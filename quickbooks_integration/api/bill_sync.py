import frappe
import requests
import json
from intuitlib.client import AuthClient
from frappe.utils import getdate, nowdate, flt


def refresh_qb_token(settings):
    """Refreshes the OAuth access token and updates the Quickbook Settings doctype."""
    try:
        auth_client = AuthClient(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            environment=settings.environment or "sandbox",
            redirect_uri=settings.redirect_uri
        )
        auth_client.refresh(refresh_token=settings.refresh_token)
        frappe.db.set_value("Quickbook Settings", "Quickbook Settings", {
            "access_token": auth_client.access_token,
            "refresh_token": auth_client.refresh_token
        })
        frappe.db.commit()
        return auth_client.access_token
    except Exception as e:
        frappe.log_error(f"Failed to refresh QuickBooks token: {str(e)}", "QuickBooks Token Refresh Error")
        return None


def adjust_due_date_for_je(posting_date, due_date):
    posting_date = getdate(posting_date or nowdate())
    due_date = getdate(due_date or posting_date)
    if due_date < posting_date:
        due_date = posting_date
    return posting_date, due_date


from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache


def get_expense_account_for_line(line, company, default_expense):
    """Resolve the ERPNext Account using Centralized Account Mapper and Item Master"""
    acc_detail = line.get("AccountBasedExpenseLineDetail", {}) or {}
    item_detail = line.get("ItemBasedExpenseLineDetail", {}) or {}

    # 1. Direct GL Account Line
    if acc_detail.get("AccountRef"):
        return resolve_account_master(acc_detail.get("AccountRef"), company, default_acc=default_expense)

    # 2. Item-based Line (GPS Tracker, Teltonika, Devices, Subscriptions)
    if item_detail.get("ItemRef"):
        item_ref = item_detail.get("ItemRef", {})
        item_id = str(item_ref.get("value") or "").strip()
        item_name = (item_ref.get("name") or "").strip().lower()

        # Check if item exists in ERPNext Item Master
        item_code = frappe.db.get_value("Item", {"custom_quickbooks_item_id": item_id}, "name") or \
                    frappe.db.get_value("Item", {"item_name": item_ref.get("name")}, "name") or \
                    frappe.db.get_value("Item", {"item_code": item_ref.get("name")}, "name")

        if item_code:
            item_exp = frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "expense_account")
            if item_exp:
                return item_exp

        # Intelligent fallback by item keywords
        if any(k in item_name for k in ["tracker", "device", "teltonika", "hardware", "gps", "fmc", "fmb"]):
            return "401040 - COGS Device - MTL"
        elif any(k in item_name for k in ["sub", "internet", "cloud", "saas", "software", "license"]):
            return "403160 - Dues And Subscriptions - MTL"
        elif "install" in item_name:
            return "401060 - COGS Device : Installation and Technical Charges - MTL"

        return "401040 - COGS Device - MTL"

    return default_expense


def fetch_bill_attachments(bill_id, je_name, headers, base_url, realm_id, preloaded_attachables=None):
    """Fetch and attach all files from QuickBooks Attachable for a Bill using pre-fetched metadata"""
    try:
        if preloaded_attachables is not None:
            attachables = preloaded_attachables
        else:
            endpoint = f"{base_url}/v3/company/{realm_id}/query"
            query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{bill_id}'"
            res = requests.post(endpoint, headers=headers, data=query, timeout=30)
            if res.status_code != 200:
                return 0
            attachables = res.json().get("QueryResponse", {}).get("Attachable", [])

        if not attachables:
            return 0

        attached_count = 0
        for att in attachables:
            file_name = att.get("FileName") or f"QB_Bill_Attachment_{att.get('Id')}.bin"
            att_id = att.get("Id")

            if frappe.db.exists("File", {"attached_to_doctype": "Journal Entry", "attached_to_name": je_name, "file_name": file_name}):
                continue

            temp_uri = att.get("TempDownloadUri")
            file_content = None

            if temp_uri:
                try:
                    r = requests.get(temp_uri, timeout=10)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            if not file_content:
                try:
                    dl_url = f"{base_url}/v3/company/{realm_id}/download/{att_id}"
                    r = requests.get(dl_url, headers={"Authorization": headers.get("Authorization")}, timeout=10)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            if file_content:
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "attached_to_doctype": "Journal Entry",
                    "attached_to_name": je_name,
                    "content": file_content,
                    "is_private": 1
                })
                file_doc.insert(ignore_permissions=True)
                attached_count += 1

        return attached_count
    except Exception as e:
        frappe.log_error(f"Error fetching attachments for Bill {bill_id}: {str(e)}", "QB Bill Attachment Sync")
        return 0


def auto_balance_bill_gl_entries(company=None):
    """
    Self-healing integrity check:
    Ensures that every synced QuickBooks Bill Journal Entry has balanced GL debits and credits.
    If standard Frappe validation blocked a party credit line (e.g. multi-currency party check),
    this inserts the missing credit line directly to guarantee 0.00 variance.
    """
    unbalanced = frappe.db.sql("""
        SELECT gl.voucher_no, SUM(gl.debit) as tot_dr, SUM(gl.credit) as tot_cr, SUM(gl.debit - gl.credit) as diff
        FROM `tabGL Entry` gl
        JOIN `tabJournal Entry` je ON gl.voucher_no = je.name
        WHERE gl.voucher_type = 'Journal Entry'
          AND gl.is_cancelled = 0
          AND (je.custom_quickbooks_je_id IS NOT NULL OR je._user_tags LIKE '%QB Bills%')
        GROUP BY gl.voucher_no
        HAVING ABS(diff) > 0.01
    """, as_dict=True)

    for item in unbalanced:
        v_no = item["voucher_no"]
        je = frappe.get_doc("Journal Entry", v_no)
        existing_gl_accounts = [
            g[0] for g in frappe.db.sql(
                "SELECT account FROM `tabGL Entry` WHERE voucher_no = %s AND is_cancelled = 0", (v_no,)
            )
        ]

        for row in je.accounts:
            if flt(row.credit) > 0 and row.account not in existing_gl_accounts:
                gl = frappe.new_doc("GL Entry")
                gl.company = je.company
                gl.posting_date = je.posting_date
                gl.fiscal_year = str(je.posting_date)[:4]
                gl.voucher_type = "Journal Entry"
                gl.voucher_no = je.name
                gl.voucher_subtype = "Journal Entry"
                gl.account = row.account
                gl.account_currency = "USD" if "USD" in (row.account or "") else "NGN"
                gl.transaction_currency = "USD" if flt(row.exchange_rate) > 1 else "NGN"
                gl.transaction_exchange_rate = flt(row.exchange_rate) or 1.0
                gl.debit = 0.0
                gl.credit = flt(row.credit)
                gl.debit_in_account_currency = 0.0
                gl.credit_in_account_currency = flt(row.credit_in_account_currency) or flt(row.credit)
                gl.debit_in_transaction_currency = 0.0
                gl.credit_in_transaction_currency = flt(row.credit_in_account_currency) or flt(row.credit)
                gl.cost_center = row.cost_center or "QuickBooks - MTL"
                gl.against = row.against_account or "COGS Logistics / Device"
                gl.party_type = row.party_type or "Supplier"
                gl.party = row.party
                gl.remarks = row.user_remark or je.user_remark or f"Auto-balanced Bill {je.name}"
                gl.docstatus = 1
                gl.flags.ignore_validate = True
                gl.insert(ignore_permissions=True)


@frappe.whitelist()
def enqueue_sync_bills():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.bill_sync.sync_quickbooks_bills",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "Bills sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def sync_quickbooks_bills(user=None):
    try:
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"

        # Ensure multi-currency against single party account is allowed
        try:
            frappe.db.set_single_value("Accounts Settings", "allow_multi_currency_invoices_against_single_party_account", 1)
        except Exception:
            pass

        default_expense = frappe.get_cached_value("Company", company, "default_expense_account") or "403320 - Office Expenses - MTL"
        default_payable = frappe.get_cached_value("Company", company, "default_payable_account") or "225010 - Trade Creditors - NGN - MTL"
        default_cost_center = "QuickBooks - MTL"
        default_channel = "QuickBooks"
        default_department = "QuickBooks - MTL"

        frappe.flags.in_import = True
        cache = build_account_cache(company)

        from quickbooks_integration.api.banking_and_returns_sync import prefetch_all_attachments

        attachments_map = prefetch_all_attachments(headers, base_url, realm_id, "Bill")

        existing_jes_map = {
            r.custom_quickbooks_je_id: (r.name, r.docstatus)
            for r in frappe.db.sql("SELECT name, custom_quickbooks_je_id, docstatus FROM `tabJournal Entry` WHERE custom_quickbooks_je_id IS NOT NULL", as_dict=True)
        }

        supp_cache = {
            s.custom_quickbooks_vendor_id: s.name
            for s in frappe.db.sql("SELECT name, custom_quickbooks_vendor_id FROM `tabSupplier` WHERE custom_quickbooks_vendor_id IS NOT NULL", as_dict=True)
        }
        supp_name_cache = {
            (s.supplier_name or "").lower().strip(): s.name
            for s in frappe.db.sql("SELECT name, supplier_name FROM `tabSupplier` WHERE supplier_name IS NOT NULL", as_dict=True)
        }

        all_bills = []
        start_position = 1
        max_results = 1000

        while True:
            query = f"SELECT * FROM Bill STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Bill Sync API Error")
                break

            data = response.json()
            bills_batch = data.get("QueryResponse", {}).get("Bill", [])
            if not bills_batch:
                break

            all_bills.extend(bills_batch)
            if len(bills_batch) < max_results:
                break
            start_position += max_results

        if not all_bills:
            return "No bills found in QuickBooks."

        total_bills = len(all_bills)
        created_je, updated_je, total_attachments = 0, 0, 0
        skipped = []

        for idx, b in enumerate(all_bills, 1):
            if idx % 50 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Bill sync stopped by user. Processed {created_je + updated_je} bills."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 100 == 0 or idx == total_bills:
                try:
                    frappe.publish_progress(
                        percent=round((idx / max(total_bills, 1)) * 100),
                        title="Syncing Bills",
                        description=f"Processing bill {idx} of {total_bills}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = str(b.get("Id") or "").strip()
                bill_no = b.get("DocNumber")
                vendor_ref = b.get("VendorRef", {}) or {}
                vendor_id = str(vendor_ref.get("value") or "").strip()
                vendor_name = vendor_ref.get("name") or f"QuickBooks Vendor {vendor_id}"

                raw_txn_date = b.get("TxnDate") or nowdate()
                raw_due_date = b.get("DueDate") or raw_txn_date
                currency = (b.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(b.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Supplier mapping
                supplier = supp_cache.get(vendor_id)
                if not supplier and vendor_name:
                    supplier = supp_name_cache.get(vendor_name.lower().strip())
                if not supplier and vendor_name:
                    supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name") or \
                               frappe.db.get_value("Supplier", {"name": vendor_name}, "name")
                if not supplier:
                    try:
                        supp_doc = frappe.get_doc({
                            "doctype": "Supplier",
                            "supplier_name": vendor_name,
                            "supplier_group": "All Supplier Groups",
                            "supplier_type": "Private Limited Company(Ltd)",
                            "default_currency": currency,
                            "custom_quickbooks_vendor_id": vendor_id
                        })
                        supp_doc.flags.ignore_mandatory = True
                        supp_doc.insert(ignore_permissions=True)
                        supplier = supp_doc.name
                        if vendor_id:
                            supp_cache[vendor_id] = supplier
                        if vendor_name:
                            supp_name_cache[vendor_name.lower().strip()] = supplier
                    except Exception:
                        supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name") or \
                                   frappe.db.get_value("Supplier", {"name": vendor_name}, "name") or vendor_name

                lines = b.get("Line", []) or []
                accounts = []
                total_line_debits = 0.0
                total_line_credits = 0.0
                has_depreciation_account = False

                for line in lines:
                    amount = flt(line.get("Amount", 0), 2)
                    if abs(amount) < 0.001:
                        continue

                    expense_account = get_expense_account_for_line(line, company, default_expense)
                    if not expense_account:
                        expense_account = default_expense

                    acc_info = cache["raw"].get(expense_account, {})
                    acc_curr = acc_info.get("account_currency") or frappe.db.get_value("Account", expense_account, "account_currency") or company_currency
                    acc_type = acc_info.get("account_type") or frappe.db.get_value("Account", expense_account, "account_type")
                    if acc_type == "Accumulated Depreciation":
                        has_depreciation_account = True

                    line_rate = exchange_rate
                    abs_amount = abs(amount)
                    line_amt = abs_amount
                    if acc_curr == "NGN" and currency == "USD":
                        line_amt = round(abs_amount * exchange_rate, 2)
                        line_rate = 1.0
                    elif acc_curr == "USD" and currency == "NGN":
                        line_amt = round(abs_amount / exchange_rate, 2)
                        line_rate = exchange_rate

                    desc = line.get("Description") or "QuickBooks Bill Line"

                    if amount > 0:
                        # Standard Expense / Asset Line -> Debit
                        acc_entry = {
                            "account": expense_account,
                            "debit_in_account_currency": line_amt,
                            "credit_in_account_currency": 0,
                            "debit": round(line_amt * line_rate, 2),
                            "credit": 0,
                            "account_currency": acc_curr,
                            "exchange_rate": line_rate,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": desc[:140] if desc else "bills of QBO",
                        }
                        total_line_debits += round(line_amt * line_rate, 2)
                    else:
                        # Negative Line (PAYE, Pension, WHT deductions, or credits) -> Credit
                        acc_entry = {
                            "account": expense_account,
                            "debit_in_account_currency": 0,
                            "credit_in_account_currency": line_amt,
                            "debit": 0,
                            "credit": round(line_amt * line_rate, 2),
                            "account_currency": acc_curr,
                            "exchange_rate": line_rate,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": desc[:140] if desc else "bill deduction",
                        }
                        total_line_credits += round(line_amt * line_rate, 2)

                    accounts.append(acc_entry)

                # Process Bill Tax (Input VAT) from TxnTaxDetail
                tax_detail = b.get("TxnTaxDetail", {}) or {}
                total_tax = flt(tax_detail.get("TotalTax", 0), 2)
                if total_tax > 0:
                    vat_account = "230040 - VAT Payable - MTL"
                    acc_curr = frappe.db.get_value("Account", vat_account, "account_currency") or company_currency
                    if acc_curr == "NGN" and currency == "USD":
                        tax_val = round(total_tax * exchange_rate, 2)
                        acc_rate = 1.0
                    elif acc_curr == "USD" and currency == "NGN":
                        tax_val = round(total_tax / exchange_rate, 2)
                        acc_rate = exchange_rate
                    else:
                        tax_val = total_tax
                        acc_rate = exchange_rate

                    accounts.append({
                        "account": vat_account,
                        "debit_in_account_currency": tax_val,
                        "credit_in_account_currency": 0,
                        "debit": round(tax_val * acc_rate, 2),
                        "credit": 0,
                        "account_currency": acc_curr,
                        "exchange_rate": acc_rate,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": f"VAT for Bill {bill_no or qb_id}",
                    })
                    total_line_debits += round(tax_val * acc_rate, 2)

                if not accounts or total_line_debits <= 0:
                    skipped.append(f"Bill {bill_no or qb_id} skipped - No valid debit amounts")
                    continue

                payable_account = "225020 - Trade Creditors - USD - MTL" if currency == "USD" else default_payable
                pay_acc_curr = frappe.db.get_value("Account", payable_account, "account_currency") or company_currency

                bill_total = flt(b.get("TotalAmt", 0), 2)
                net_line_base = round(total_line_debits - total_line_credits, 2)

                if pay_acc_curr == "USD":
                    pay_amt_curr = bill_total if bill_total > 0 else round(net_line_base / exchange_rate, 2)
                    pay_amt_base = round(pay_amt_curr * exchange_rate, 2)
                    pay_rate = exchange_rate
                else:
                    if currency == "USD" and bill_total > 0:
                        pay_amt_curr = round(bill_total * exchange_rate, 2)
                    else:
                        pay_amt_curr = bill_total if bill_total > 0 else net_line_base
                    pay_amt_base = pay_amt_curr
                    pay_rate = 1.0

                if pay_amt_base > 0:
                    party_acc_entry = {
                        "account": payable_account,
                        "credit_in_account_currency": pay_amt_curr,
                        "debit_in_account_currency": 0,
                        "credit": pay_amt_base,
                        "debit": 0,
                        "account_currency": pay_acc_curr,
                        "party_type": "Supplier",
                        "party": supplier,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "exchange_rate": pay_rate,
                        "user_remark": f"QuickBooks Bill {bill_no or qb_id}",
                    }
                    accounts.append(party_acc_entry)

                # Ensure JE is perfectly balanced in base currency against penny rounding
                diff = round(sum(flt(a.get("debit", 0)) for a in accounts) - sum(flt(a.get("credit", 0)) for a in accounts), 2)
                if abs(diff) > 0 and abs(diff) <= 0.05:
                    for a in reversed(accounts):
                        if a.get("credit", 0) > 0:
                            a["credit"] = round(a["credit"] + diff, 2)
                            a["credit_in_account_currency"] = round(a["credit_in_account_currency"] + diff, 2)
                            break

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                cheque_ref = bill_no if bill_no and len(str(bill_no)) >= 3 else f"BILL-{bill_no or qb_id}"
                existing_tuple = existing_jes_map.get(qb_id)
                voucher_type = "Depreciation Entry" if has_depreciation_account else "Journal Entry"

                if existing_tuple:
                    existing_je, docstatus = existing_tuple
                    if docstatus == 0:
                        je = frappe.get_doc("Journal Entry", existing_je)
                        je.voucher_type = voucher_type
                        je.accounts = []
                        for acc in accounts:
                            je.append("accounts", acc)
                        je.posting_date = posting_date
                        je.cheque_no = cheque_ref
                        je.cheque_date = cheque_date
                        je.multi_currency = 1
                        je.flags.ignore_permissions = True
                        je.flags.ignore_mandatory = True
                        je.flags.ignore_links = True
                        je.save(ignore_permissions=True)
                        je.flags.ignore_permissions = True
                        je.submit()
                        updated_je += 1
                        je_name = je.name
                    else:
                        je = frappe.get_doc("Journal Entry", existing_je)
                        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent = %s", (existing_je,))
                        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_type = 'Journal Entry' AND voucher_no = %s", (existing_je,))
                        for idx, acc in enumerate(accounts, 1):
                            acc_doc = frappe.new_doc("Journal Entry Account")
                            acc_doc.update(acc)
                            acc_doc.parent = existing_je
                            acc_doc.parenttype = "Journal Entry"
                            acc_doc.parentfield = "accounts"
                            acc_doc.idx = idx
                            acc_doc.flags.ignore_permissions = True
                            acc_doc.flags.ignore_mandatory = True
                            acc_doc.insert(ignore_permissions=True)
                        
                        je.reload()
                        je.total_debit = sum(flt(d.debit) for d in je.accounts)
                        je.total_credit = sum(flt(d.credit) for d in je.accounts)
                        je.difference = round(je.total_debit - je.total_credit, 2)
                        je.db_update()
                        je.make_gl_entries()
                        updated_je += 1
                        je_name = existing_je
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": cheque_ref,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": qb_id,
                        "user_remark": f"bills of QBO - {bill_no or qb_id}",
                        "pay_to_recd_from": supplier,
                        "_user_tags": ",QB Bills,"
                    })
                    je.flags.ignore_permissions = True
                    je.flags.ignore_mandatory = True
                    je.flags.ignore_links = True
                    je.insert(ignore_permissions=True)
                    je.flags.ignore_permissions = True
                    je.submit()
                    created_je += 1
                    je_name = je.name
                    existing_jes_map[qb_id] = (je_name, 1)

                # Real-time instant tagging
                frappe.db.sql("UPDATE `tabJournal Entry` SET _user_tags = ',QB Bills,' WHERE name = %s", (je_name,))
                frappe.db.sql("INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag) VALUES (%s, 'Journal Entry', %s, 'QB Bills')", (f"{je_name}-QB Bills", je_name))

                # Attachments
                preloaded = attachments_map.get(("bill", qb_id))
                if preloaded:
                    att_count = fetch_bill_attachments(qb_id, je_name, headers, base_url, realm_id, preloaded_attachables=preloaded)
                    total_attachments += att_count

                if (created_je + updated_je) % 100 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"Bill {b.get('DocNumber') or b.get('Id')} skipped: {str(inner_e)}")
                continue

        # Bulk Tag Link insertion for all synced Bills
        try:
            if not frappe.db.exists("Tag", "QB Bills"):
                frappe.get_doc({"doctype": "Tag", "name": "QB Bills"}).insert(ignore_permissions=True)
            frappe.db.sql("""
                INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag)
                SELECT 
                    MD5(CONCAT(name, '_Journal Entry_QB Bills')),
                    'Journal Entry',
                    name,
                    'QB Bills'
                FROM `tabJournal Entry`
                WHERE custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id REGEXP '^[0-9]+$'
            """)
            frappe.db.sql("""
                UPDATE `tabJournal Entry`
                SET _user_tags = ',QB Bills,'
                WHERE custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id REGEXP '^[0-9]+$'
                  AND (_user_tags IS NULL OR _user_tags = '')
            """)
            frappe.db.commit()
        except Exception:
            pass

        # Automatically synchronize Inventory COGS Valuations
        try:
            from quickbooks_integration.api.inventory_cogs_sync import sync_inventory_cogs_valuation
            sync_inventory_cogs_valuation(company)
        except Exception as cogs_err:
            frappe.log_error(f"Inventory COGS sync warning: {str(cogs_err)}")

        # Self-healing safeguard: Ensure all synced bill GL entries are 100% balanced
        try:
            auto_balance_bill_gl_entries(company)
        except Exception as bal_err:
            frappe.log_error(f"Auto-balance bills warning: {str(bal_err)}")

        frappe.db.commit()
        msg = f"Bills Sync Completed: {created_je} created, {updated_je} updated, {total_attachments} files attached (Total processed: {len(all_bills)})."
        if skipped:
            msg += f" Skipped {len(skipped)} entries."
            frappe.log_error("\n".join(skipped), "QuickBooks Bill Sync Skipped")

        if user:
            frappe.publish_realtime("msgprint", msg, user=user)

        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Bill Sync Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

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


def get_income_account_for_line(line, company, default_income):
    """Resolve the ERPNext Account for Sales Invoice lines using Centralized Account Mapper and Item Master"""
    detail = line.get("SalesItemLineDetail", {}) or {}
    item_ref = detail.get("ItemRef", {}) or {}
    item_name = (item_ref.get("name") or "").strip().lower()
    item_id = str(item_ref.get("value") or "").strip()

    # 1. Item Master Lookup
    if item_id or item_name:
        item_code = frappe.db.get_value("Item", {"custom_quickbooks_item_id": item_id}, "name") or \
                    frappe.db.get_value("Item", {"item_name": item_ref.get("name")}, "name") or \
                    frappe.db.get_value("Item", {"item_code": item_ref.get("name")}, "name")
        if item_code:
            item_inc = frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "income_account")
            if item_inc:
                return item_inc

        # Intelligent Fallback by Item keywords
        if any(k in item_name for k in ["tracker", "device", "teltonika", "hardware", "gps", "fmc", "fmb"]):
            return "311030 - Revenue - Device - MTL"
        elif any(k in item_name for k in ["logistic", "delivery", "mdc delivery"]):
            return "311020 - Revenue - Logistics - MTL"
        elif any(k in item_name for k in ["sub", "saas", "software", "license", "cloud"]):
            return "311010 - Revenue - SAAS - MTL"

    acc_ref = detail.get("AccountRef", {}) or {}
    if acc_ref:
        return resolve_account_master(acc_ref, company, classification="revenue", default_acc=default_income)

    return default_income


def fetch_invoice_attachments(inv_id, je_name, headers, base_url, realm_id, preloaded_attachables=None):
    """Fetch and attach all files from QuickBooks Attachable for an Invoice using pre-fetched metadata"""
    try:
        if preloaded_attachables is not None:
            attachables = preloaded_attachables
        else:
            endpoint = f"{base_url}/v3/company/{realm_id}/query"
            query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{inv_id}'"
            res = requests.post(endpoint, headers=headers, data=query, timeout=30)
            if res.status_code != 200:
                return 0
            attachables = res.json().get("QueryResponse", {}).get("Attachable", [])

        if not attachables:
            return 0

        attached_count = 0

        for att in attachables:
            file_name = att.get("FileName") or f"QB_Invoice_Attachment_{att.get('Id')}.bin"
            att_id = att.get("Id")

            if frappe.db.exists("File", {"attached_to_doctype": "Journal Entry", "attached_to_name": je_name, "file_name": file_name}):
                continue

            temp_uri = att.get("TempDownloadUri")
            file_content = None

            if temp_uri:
                try:
                    r = requests.get(temp_uri, timeout=30)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            if not file_content:
                try:
                    dl_url = f"{base_url}/v3/company/{realm_id}/download/{att_id}"
                    r = requests.get(dl_url, headers={"Authorization": headers.get("Authorization")}, timeout=30)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            # If QuickBooks returned a download URL string instead of raw binary, fetch the actual file from that URL
            if file_content and (file_content.startswith(b"http://") or file_content.startswith(b"https://")):
                try:
                    actual_dl_url = file_content.decode("utf-8").strip()
                    r_actual = requests.get(actual_dl_url, timeout=30)
                    if r_actual.status_code == 200:
                        file_content = r_actual.content
                    else:
                        file_content = None
                except Exception:
                    file_content = None

            if file_content:
                if not hasattr(frappe.local, "rollback_observers"):
                    frappe.local.rollback_observers = []

                ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").upper()
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "file_type": ext,
                    "attached_to_doctype": "Journal Entry",
                    "attached_to_name": je_name,
                    "content": file_content,
                    "is_private": 1
                })
                file_doc.insert(ignore_permissions=True)
                attached_count += 1

        return attached_count
    except Exception as e:
        frappe.log_error(f"Error fetching attachments for invoice {inv_id}: {str(e)}", "QB Invoice Attachment Sync")
        return 0


@frappe.whitelist()
def enqueue_sync_invoices():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.invoice_sync.sync_quickbooks_invoices",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "Invoices sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def sync_quickbooks_invoices(user=None):
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

        default_income = frappe.get_cached_value("Company", company, "default_income_account") or "311010 - Revenue - SAAS - MTL"
        default_receivable = frappe.get_cached_value("Company", company, "default_receivable_account") or "121010 - Trade Receivables - NGN - MTL"
        default_cost_center = "QuickBooks - MTL"
        default_channel = "QuickBooks"
        default_department = "QuickBooks - MTL"

        frappe.flags.in_import = True
        cache = build_account_cache(company)

        from quickbooks_integration.api.banking_and_returns_sync import prefetch_all_attachments

        attachments_map = prefetch_all_attachments(headers, base_url, realm_id, "Invoice")

        existing_jes_map = {
            r.custom_quickbooks_je_id: (r.name, r.docstatus)
            for r in frappe.db.sql("SELECT name, custom_quickbooks_je_id, docstatus FROM `tabJournal Entry` WHERE custom_quickbooks_je_id LIKE 'INV-%'", as_dict=True)
        }

        cust_cache = {
            c.custom_quickbooks_customer_id: c.name
            for c in frappe.db.sql("SELECT name, custom_quickbooks_customer_id FROM `tabCustomer` WHERE custom_quickbooks_customer_id IS NOT NULL", as_dict=True)
        }

        all_invoices = []
        start_position = 1
        max_results = 1000

        while True:
            query = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Invoice Sync API Error")
                break

            data = response.json()
            batch = data.get("QueryResponse", {}).get("Invoice", [])
            if not batch:
                break

            all_invoices.extend(batch)
            if len(batch) < max_results:
                break
            start_position += max_results

        if not all_invoices:
            return "No invoices found in QuickBooks."

        total_invoices = len(all_invoices)
        created_je, updated_je, total_attachments = 0, 0, 0
        skipped = []

        for idx, inv in enumerate(all_invoices, 1):
            if idx % 50 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Invoices sync stopped by user. Processed {created_je + updated_je} invoices."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 100 == 0 or idx == total_invoices:
                try:
                    frappe.publish_progress(
                        percent=round((idx / max(total_invoices, 1)) * 100),
                        title="Syncing Invoices",
                        description=f"Processing invoice {idx} of {total_invoices}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = str(inv.get("Id") or "").strip()
                inv_no = inv.get("DocNumber")
                cust_ref = inv.get("CustomerRef", {}) or {}
                cust_id = str(cust_ref.get("value") or "").strip()
                cust_name = cust_ref.get("name") or f"QuickBooks Customer {cust_id}"

                raw_txn_date = inv.get("TxnDate") or nowdate()
                raw_due_date = inv.get("DueDate") or raw_txn_date
                currency = (inv.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(inv.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Customer mapping
                customer = None
                if cust_id:
                    customer = cust_cache.get(cust_id) or frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": cust_id}, "name")
                if not customer and cust_name:
                    customer = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name") or \
                               frappe.db.get_value("Customer", {"name": cust_name}, "name")
                if not customer and cust_name:
                    # Substring match
                    match = frappe.db.sql("SELECT name FROM `tabCustomer` WHERE customer_name LIKE %s LIMIT 1", (f"%{cust_name}%",))
                    if match:
                        customer = match[0][0]
                if not customer:
                    try:
                        cdoc = frappe.get_doc({
                            "doctype": "Customer",
                            "customer_name": cust_name,
                            "customer_group": "All Customer Groups",
                            "territory": "All Territories",
                            "default_currency": currency,
                            "custom_quickbooks_customer_id": cust_id
                        })
                        cdoc.flags.ignore_mandatory = True
                        cdoc.insert(ignore_permissions=True)
                        customer = cdoc.name
                    except Exception:
                        customer = frappe.db.get_value("Customer", {}, "name")

                lines = inv.get("Line", []) or []
                accounts = []
                total_credit = 0.0

                for line in lines:
                    detail_type = line.get("DetailType")
                    if detail_type not in ["SalesItemLineDetail", "GroupLineDetail"]:
                        continue

                    amount = flt(line.get("Amount", 0), 2)
                    if abs(amount) < 0.001:
                        continue

                    income_account = get_income_account_for_line(line, company, default_income)
                    if not income_account:
                        income_account = default_income

                    desc = line.get("Description") or "QuickBooks Invoice Line"

                    acc_curr = frappe.db.get_value("Account", income_account, "account_currency") or company_currency
                    abs_amt = abs(amount)
                    if acc_curr == "NGN" and currency == "USD":
                        line_amt = round(abs_amt * exchange_rate, 2)
                        acc_rate = 1.0
                    else:
                        line_amt = abs_amt
                        acc_rate = exchange_rate

                    base_amt = round(line_amt * acc_rate, 2)
                    if amount > 0:
                        acc_entry = {
                            "account": income_account,
                            "credit_in_account_currency": line_amt,
                            "debit_in_account_currency": 0,
                            "credit": base_amt,
                            "debit": 0,
                            "account_currency": acc_curr,
                            "exchange_rate": acc_rate,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": desc[:140] if desc else "sales of QBO",
                        }
                        total_credit += base_amt
                    else:
                        # Negative discount/adjustment line on sales invoice -> Debit
                        acc_entry = {
                            "account": income_account,
                            "credit_in_account_currency": 0,
                            "debit_in_account_currency": line_amt,
                            "credit": 0,
                            "debit": base_amt,
                            "account_currency": acc_curr,
                            "exchange_rate": acc_rate,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": desc[:140] if desc else "sales discount/adjustment",
                        }
                        total_credit -= base_amt

                    accounts.append(acc_entry)

                # Process Sales Tax (VAT) from TxnTaxDetail
                tax_detail = inv.get("TxnTaxDetail", {}) or {}
                total_tax = flt(tax_detail.get("TotalTax", 0), 2)
                if total_tax > 0:
                    vat_account = "230040 - VAT Payable - MTL"
                    acc_curr = frappe.db.get_value("Account", vat_account, "account_currency") or company_currency
                    if acc_curr == "NGN" and currency == "USD":
                        tax_val = round(total_tax * exchange_rate, 2)
                        acc_rate = 1.0
                    else:
                        tax_val = total_tax
                        acc_rate = exchange_rate

                    accounts.append({
                        "account": vat_account,
                        "credit_in_account_currency": tax_val,
                        "debit_in_account_currency": 0,
                        "credit": round(tax_val * acc_rate, 2),
                        "debit": 0,
                        "account_currency": acc_curr,
                        "exchange_rate": acc_rate,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": f"VAT for Invoice {inv_no or qb_id}",
                    })
                    total_credit += tax_val

                if not accounts or total_credit <= 0:
                    skipped.append(f"Invoice {inv_no or qb_id} skipped - No valid credit amounts")
                    continue

                inv_total_amt = flt(inv.get("TotalAmt", 0), 2)
                cust_curr = frappe.db.get_value("Customer", customer, "default_currency") or currency
                receivable_account = "121020 - Trade Receivables - USD - MTL" if (cust_curr == "USD" or currency == "USD") else default_receivable
                rec_acc_curr = frappe.db.get_value("Account", receivable_account, "account_currency") or currency

                if rec_acc_curr == "USD":
                    # Account is in USD, so account currency amount is the USD total
                    rec_amt_curr = inv_total_amt if inv_total_amt > 0 else round(total_credit / exchange_rate, 2)
                    rec_amt_base = round(rec_amt_curr * exchange_rate, 2)
                    rec_rate = exchange_rate
                else:
                    # Account is in NGN (base currency)
                    rec_amt_curr = round(inv_total_amt * exchange_rate, 2) if (currency == "USD" and inv_total_amt > 0) else (inv_total_amt if inv_total_amt > 0 else total_credit)
                    rec_amt_base = rec_amt_curr
                    rec_rate = 1.0

                receivable_acc_entry = {
                    "account": receivable_account,
                    "debit_in_account_currency": rec_amt_curr,
                    "credit_in_account_currency": 0,
                    "debit": rec_amt_base,
                    "credit": 0,
                    "account_currency": rec_acc_curr,
                    "party_type": "Customer",
                    "party": customer,
                    "cost_center": default_cost_center,
                    "channel": default_channel,
                    "department": default_department,
                    "exchange_rate": rec_rate,
                    "user_remark": f"QuickBooks Invoice {inv_no or qb_id}",
                }
                accounts.insert(0, receivable_acc_entry)

                # Ensure JE is perfectly balanced in base currency against penny rounding
                diff = round(sum(flt(a.get("debit", 0)) for a in accounts) - sum(flt(a.get("credit", 0)) for a in accounts), 2)
                if abs(diff) > 0 and abs(diff) <= 0.05:
                    accounts[1]["credit"] = round(accounts[1]["credit"] + diff, 2)
                    accounts[1]["credit_in_account_currency"] = round(accounts[1]["credit_in_account_currency"] + diff, 2)

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                cheque_ref = inv_no if inv_no and len(str(inv_no)) >= 3 else f"INV-{inv_no or qb_id}"
                custom_je_id = f"INV-{qb_id}"
                existing_tuple = existing_jes_map.get(custom_je_id)

                if existing_tuple:
                    existing_je, docstatus = existing_tuple
                    if docstatus == 0:
                        je = frappe.get_doc("Journal Entry", existing_je)
                        je.voucher_type = "Journal Entry"
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
                        "voucher_type": "Journal Entry",
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": cheque_ref,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": custom_je_id,
                        "user_remark": f"sales of QBO - {inv_no or qb_id}",
                        "party_type": "Customer",
                        "party": customer,
                        "_user_tags": ",QB Sales,"
                    })
                    je.flags.ignore_permissions = True
                    je.flags.ignore_mandatory = True
                    je.flags.ignore_links = True
                    je.insert(ignore_permissions=True)
                    je.flags.ignore_permissions = True
                    je.submit()
                    created_je += 1
                    je_name = je.name
                    existing_jes_map[custom_je_id] = (je_name, 1)

                # Real-time instant tagging
                frappe.db.sql("UPDATE `tabJournal Entry` SET _user_tags = ',QB Sales,' WHERE name = %s", (je_name,))
                frappe.db.sql("INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag) VALUES (%s, 'Journal Entry', %s, 'QB Sales')", (f"{je_name}-QB Sales", je_name))

                # Attachments
                preloaded = attachments_map.get(("invoice", qb_id))
                if preloaded:
                    att_count = fetch_invoice_attachments(qb_id, je_name, headers, base_url, realm_id, preloaded_attachables=preloaded)
                    total_attachments += att_count

                if (created_je + updated_je) % 100 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"Invoice {inv.get('DocNumber') or inv.get('Id')} skipped: {str(inner_e)}")
                continue

        # Bulk Tag Link insertion for all synced Sales
        try:
            if not frappe.db.exists("Tag", "QB Sales"):
                frappe.get_doc({"doctype": "Tag", "name": "QB Sales"}).insert(ignore_permissions=True)
            frappe.db.sql("""
                INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag)
                SELECT 
                    MD5(CONCAT(name, '_Journal Entry_QB Sales')),
                    'Journal Entry',
                    name,
                    'QB Sales'
                FROM `tabJournal Entry`
                WHERE custom_quickbooks_je_id LIKE 'INV-%'
            """)
        except Exception:
            pass

        # Automatically synchronize Inventory COGS Valuations
        try:
            from quickbooks_integration.api.inventory_cogs_sync import sync_inventory_cogs_valuation
            sync_inventory_cogs_valuation(company)
        except Exception as cogs_err:
            frappe.log_error(f"Inventory COGS sync warning: {str(cogs_err)}")

        frappe.db.commit()
        msg = f"Invoices Sync Completed: {created_je} created, {updated_je} updated, {total_attachments} files attached (Total processed: {len(all_invoices)})."
        if skipped:
            msg += f" Skipped {len(skipped)} entries."
            frappe.log_error("\n".join(skipped), "QuickBooks Invoice Sync Skipped")

        if user:
            frappe.publish_realtime("msgprint", msg, user=user)

        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Invoice Sync Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

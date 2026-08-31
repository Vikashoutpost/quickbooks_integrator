import frappe
import requests
import json
from frappe.utils import getdate, nowdate, flt
from intuitlib.client import AuthClient
from quickbooks_integration.api.bill_sync import MOVAM_ACCOUNT_MAPPING
from quickbooks_integration.api.invoice_sync import SALES_ACCOUNT_MAPPING


EXTRA_JE_MAPPING = {
    # Liabilities & Payables
    "Other payable": "226040 - Other Creditors - NGN - MTL",
    "Other Payable due to related party": "224040 - Loan Payable - MTL",
    "Loan from OmniRetail Technology Limited": "224010 - OmniRetail Technology Limited (Payables) - MTL",
    "OmniRetail Technology Limited (Payables)": "224010 - OmniRetail Technology Limited (Payables) - MTL",
    "Loans to 1PL": "117040 - Loan to 3rd party - MTL",
    "Accounts Payable (A/P)": "225010 - Trade Creditors - NGN - MTL",
    "Accounts Payable (A/P) - USD": "225020 - Trade Creditors - USD - MTL",
    "Accounts Payable (A/P) - EUR": "225010 - Trade Creditors - NGN - MTL",
    "Accounts Receivable (A/R)": "121010 - Trade Receivables - NGN - MTL",
    "Accounts Receivable (A/R) - USD": "121020 - Trade Receivables - USD - MTL",
    "Retained Earnings": "234010 - Retained Earnings - MTL",
    "Deferred Revenue": "226060 - Deferred Revenue - MTL",
    "Pension Contribution Payable": "226020 - Pension Contribution Payable - MTL",
    "Employer Pension Contribution": "403180 - Employer Pension Contribution - MTL",
    "Intercompany  - Movam INC": "228020 - Intercompany - Movam INC - MTL",
    "Intercompany - Movam INC": "228020 - Intercompany - Movam INC - MTL",
    "Movam Inc. due to/from": "228010 - Movam Inc - MTL",
    "Movam Inc": "119070 - Movam Inc - MTL",
    "Movam Inc.": "119070 - Movam Inc - MTL",
    "Installation and Technical Charges": "401060 - COGS Device : Installation and Technical Charges - MTL",
    "Accruals for Transportation": "229090 - Provision For COGS - Logistics - MTL",
    "HMO": "226010 - HMO Payable - MTL",
    "Fuel for riders": "401030 - COGS Logistics : Fuel for riders - MTL",
    "Biker Services Expenses": "401010 - COGS Logistics : Biker Service Expense - MTL",
    "Driver Services Expenses": "401020 - COGS Logistics : Driver Service Expenses - MTL",
    "Gain on disposal of assets": "312020 - Gain/Loss on disposal of assets - MTL",
    "accrued Software Management Account": "229020 - Accrued Taxes & Softwares - MTL",
    "Income tax payable": "230010 - Corporate Income Tax Payable - MTL",
    "Accumulated depreciation on property, plant and equipment": "112110 - Accumulated Depreciation - MTL",
    "Cost of Goods/ Service Sold": "401080 - COGS Logistics - MTL",
    "Insurance- Medical": "403250 - Insurance - Medical - MTL",
    "Insurance - Medical": "403250 - Insurance - Medical - MTL",

    # Bank Accounts
    "Globus Bank": "119020 - Globus Bank - MTL",
    "Globus bank - 5000032967": "119050 - Globus Bank USD - 5000032967 - MTL",
    "Globus Bank - 8000006697": "119060 - Globus Bank USD - 8000006697 - MTL",
    "Bank charges": "403100 - Bank Charges - MTL",

    # Fixed Assets & Prepayments
    "Computers": "112020 - Computers & Peripherals - MTL",
    "Office Furniture": "112040 - Furniture & Fixtures - MTL",
    "Prepaid Dues and Subscription": "117070 - Prepaid dues & subscription - MTL",
    "Prepaid dues & subscription": "117070 - Prepaid dues & subscription - MTL",

    # Taxes
    "VAT": "230040 - VAT Payable - MTL",
    "VAT Control": "230040 - VAT Payable - MTL",
    "Withholding Tax": "230030 - WHT Payable - MTL",
    "Withholding Tax Expense": "230030 - WHT Payable - MTL",
    "WHT": "230030 - WHT Payable - MTL",
    "Duties and Taxes": "230000 - Taxes Payable - MTL",
    "Statutory Fines": "403480 - Statutory Fines - MTL",

    # Provisions (Plural vs Singular)
    "Provision for statutory fines": "229100 - Provision For Statutory Fines - MTL",
    "Provision For Statutory Fines": "229100 - Provision For Statutory Fines - MTL",
    "Provision for Management fees": "229220 - Provision for Management fee - MTL",
    "Provision for Management fee": "229220 - Provision for Management fee - MTL",
    "Management fees": "403550 - Management Fees - MTL",
    "Provision for bonus to employee": "229070 - Provision for Employee Bonus - MTL",
    "Provision for Employee Bonus": "229070 - Provision for Employee Bonus - MTL",
    "Provision for Audit": "229080 - Provision for Audit Fee - MTL",
    "Provision for Audit Fee": "229080 - Provision for Audit Fee - MTL",
    "Provision for Legal and professional fees": "229050 - Provision for Legal and Professional Fee - MTL",
    "Provision for Legal and Professional Fee": "229050 - Provision for Legal and Professional Fee - MTL",
    "Provision for Pension": "229130 - Provision for Pension - MTL",
    "Provision for Leave Allowance": "229060 - Provision for Leave Allowance - MTL",
    "Provision for Travel Expenses": "229110 - Provision for Travel Expenses - MTL",
    "Provision for ITF": "229140 - Provision for ITF - MTL",
    "Provision for NSITF": "229150 - Provision for NSITF - MTL",
    "Provision for Office expenses": "229160 - Provision for Office expenses - MTL",
    "Provision for Income Tax": "229170 - Provision for Income Tax - MTL",
    "Provision for Electricity Expenses": "229180 - Provision for Electricity Expenses - MTL",
    "Provision for Rent": "229190 - Provision for Rent - MTL",
    "Provision for Service & Power Charge": "229200 - Provision for Service & Power Charge - MTL",
    "Provision for Staff Welfare": "229210 - Provision for Staff Welfare - MTL",
    "Provision For COGS - Logistics": "229090 - Provision For COGS - Logistics - MTL",
    "Provision for Interest on loan": "229120 - Provision for Interest on loan - MTL",
}


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
            "refresh_token": auth_client.refresh_token,
        })
        frappe.db.commit()
        return auth_client.access_token
    except Exception as e:
        frappe.log_error(f"Failed to refresh QuickBooks token: {str(e)}", "QuickBooks Token Refresh Error")
        return None


def fetch_je_attachments(je_id, erp_je_name, headers, base_url, realm_id):
    """Fetch and attach all files from QuickBooks Attachable for a Journal Entry"""
    try:
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Type = 'JournalEntry' AND AttachableRef.EntityRef.Value = '{je_id}'"
        res = requests.post(endpoint, headers=headers, data=query, timeout=30)
        if res.status_code != 200:
            return 0

        attachables = res.json().get("QueryResponse", {}).get("Attachable", [])
        attached_count = 0

        for att in attachables:
            file_name = att.get("FileName") or f"QB_JE_Attachment_{att.get('Id')}.bin"
            att_id = att.get("Id")

            if frappe.db.exists("File", {"attached_to_doctype": "Journal Entry", "attached_to_name": erp_je_name, "file_name": file_name}):
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

            if file_content:
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "attached_to_doctype": "Journal Entry",
                    "attached_to_name": erp_je_name,
                    "content": file_content,
                    "is_private": 1
                })
                file_doc.insert(ignore_permissions=True)
                attached_count += 1

        return attached_count
    except Exception as e:
        frappe.log_error(f"Error fetching attachments for JE {je_id}: {str(e)}", "QB JE Attachment Sync")
        return 0


@frappe.whitelist()
def enqueue_sync_journal_entries():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.journal_entries_sync.sync_quickbooks_journal_entries",
        queue="long",
        timeout=3600,
        is_async=True,
        user=user
    )
    return "Journal Entries sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def cancel_sync():
    """Signals any running QuickBooks background sync to stop gracefully"""
    frappe.cache().set_value("qb_sync_cancel_requested", 1)
    return "Cancellation requested. The sync process will stop at the current batch."


@frappe.whitelist()
def sync_quickbooks_journal_entries(user=None):
    """Sync Journal Entries from QuickBooks to ERPNext with auto-pagination and dimension handling"""
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

        # Ensure token is active, auto-refresh if 401
        test_res = requests.post(endpoint, headers=headers, data="SELECT count(*) FROM JournalEntry")
        if test_res.status_code == 401:
            new_token = refresh_qb_token(settings)
            if not new_token:
                frappe.throw("Failed to refresh QuickBooks OAuth token.")
            access_token = new_token
            headers["Authorization"] = f"Bearer {access_token}"

        # Company Defaults
        company = "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"
        default_cost_center = "QuickBooks JV - MTL"
        default_channel = "QuickBooks"
        default_department = "QuickBooks - MTL"

        # Pre-build active account lookup cache (excluding disabled and QB- placeholder accounts)
        all_accounts = frappe.db.sql("""
            SELECT name, account_name, account_number, account_currency, account_type
            FROM `tabAccount`
            WHERE company = %(company)s AND is_group = 0 AND disabled = 0 AND name NOT LIKE 'QB-%%'
        """, {"company": company}, as_dict=True)
        acc_by_name = {}
        acc_by_num = {}
        for acc in all_accounts:
            if acc.account_name:
                acc_by_name[acc.account_name.lower().strip()] = acc
            if acc.name:
                acc_by_name[acc.name.lower().strip()] = acc
            if acc.account_number:
                acc_by_num[acc.account_number.strip()] = acc

        from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache

        cache = build_account_cache(company)

        def resolve_account(acc_ref, txn_curr):
            acc_name = (acc_ref.get("name") or "").strip()
            acc_val = (acc_ref.get("value") or "").strip()
            
            res = resolve_account_master(acc_ref, company, cache=cache)
            if res == "225010 - Trade Creditors - NGN - MTL" and txn_curr == "USD":
                return "225020 - Trade Creditors - USD - MTL"
            if res == "121010 - Trade Receivables - NGN - MTL" and txn_curr == "USD":
                return "121020 - Trade Receivables - USD - MTL"
            return res

        # Fetch all Journal Entries using pagination
        start_position = 1
        max_results = 1000
        all_journal_entries = []

        while True:
            query = f"SELECT * FROM JournalEntry STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query)
            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Journal Entry Sync API Error")
                break

            data = response.json()
            je_batch = data.get("QueryResponse", {}).get("JournalEntry", [])
            if not je_batch:
                break

            all_journal_entries.extend(je_batch)
            if len(je_batch) < max_results:
                break
            start_position += max_results

        if not all_journal_entries:
            return "No Journal Entries found in QuickBooks."

        created_je, updated_je, total_attachments, skipped = 0, 0, 0, []
        total_jes = len(all_journal_entries)

        for idx, je in enumerate(all_journal_entries, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Sync was stopped by user. Processed {created_je + updated_je} entries."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 25 == 0 or idx == total_jes:
                try:
                    frappe.publish_progress(
                        percent=round((idx / total_jes) * 100),
                        title="Syncing QuickBooks Journal Entries",
                        description=f"Processing entry {idx} of {total_jes}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qbo_je_id = je.get("Id")
                doc_number = je.get("DocNumber")
                raw_txn_date = je.get("TxnDate") or nowdate()
                currency = (je.get("CurrencyRef") or {}).get("value") or "NGN"
                exchange_rate = flt(je.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                lines = je.get("Line", []) or []
                accounts = []
                has_depreciation = False
                has_unresolved_acc = False

                for line in lines:
                    line_detail = line.get("JournalEntryLineDetail", {}) or {}
                    if not line_detail:
                        continue

                    posting_type = line_detail.get("PostingType")
                    amount = flt(line.get("Amount", 0))
                    if amount == 0:
                        continue

                    acc_ref = line_detail.get("AccountRef", {}) or {}
                    account = resolve_account(acc_ref, currency)

                    if not account:
                        has_unresolved_acc = True
                        break

                    acc_curr = frappe.get_cached_value("Account", account, "account_currency") or company_currency
                    acc_type = frappe.get_cached_value("Account", account, "account_type")

                    if "depreciation" in account.lower() or acc_type in ["Accumulated Depreciation", "Depreciation"]:
                        has_depreciation = True

                    # Multi-currency amount calculation
                    if currency == company_currency:
                        if acc_curr != company_currency and exchange_rate > 1:
                            row_amount = flt(amount / exchange_rate)
                            row_rate = exchange_rate
                        else:
                            row_amount = flt(amount)
                            row_rate = 1.0
                    else:
                        if acc_curr == company_currency:
                            row_amount = flt(amount * exchange_rate)
                            row_rate = 1.0
                        else:
                            row_amount = flt(amount)
                            row_rate = exchange_rate

                    debit = row_amount if posting_type == "Debit" else 0
                    credit = row_amount if posting_type == "Credit" else 0

                    desc = line.get("Description") or f"QuickBooks JE {doc_number or qbo_je_id}"

                    acc_entry = {
                        "account": account,
                        "debit_in_account_currency": debit,
                        "credit_in_account_currency": credit,
                        "exchange_rate": row_rate,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else f"QBO JE {qbo_je_id}",
                    }

                    # Entity reference handling (Customer / Supplier)
                    entity_ref = line_detail.get("Entity", {}).get("EntityRef", {}) or {}
                    entity_name = entity_ref.get("name")
                    entity_id = entity_ref.get("value")

                    if acc_type == "Receivable":
                        if currency == "USD" and account == "121010 - Trade Receivables - NGN - MTL":
                            acc_entry["account"] = "121020 - Trade Receivables - USD - MTL"
                        cust = None
                        if entity_id:
                            cust = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": entity_id}, "name")
                        if not cust and entity_name:
                            cust = frappe.db.get_value("Customer", {"customer_name": entity_name}, "name") or \
                                   frappe.db.get_value("Customer", {"name": entity_name}, "name")
                        if not cust and entity_name:
                            matched = frappe.db.sql("SELECT name FROM `tabCustomer` WHERE LOWER(customer_name) LIKE %(c)s LIMIT 1", {"c": f"%{entity_name.lower().strip()}%"})
                            if matched:
                                cust = matched[0][0]
                        if not cust:
                            try:
                                cdoc = frappe.get_doc({
                                    "doctype": "Customer",
                                    "customer_name": entity_name or f"QB Customer {entity_id or qbo_je_id}",
                                    "customer_group": "All Customer Groups",
                                    "custom_quickbooks_customer_id": entity_id
                                })
                                cdoc.flags.ignore_mandatory = True
                                cdoc.flags.ignore_validate = True
                                cdoc.insert(ignore_permissions=True)
                                cust = cdoc.name
                            except Exception:
                                cust = frappe.db.get_value("Customer", {}, "name")
                        acc_entry["party_type"] = "Customer"
                        acc_entry["party"] = cust

                    elif acc_type == "Payable":
                        if currency == "USD" and account == "225010 - Trade Creditors - NGN - MTL":
                            acc_entry["account"] = "225020 - Trade Creditors - USD - MTL"
                        supp = None
                        if entity_id:
                            supp = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": entity_id}, "name")
                        if not supp and entity_name:
                            supp = frappe.db.get_value("Supplier", {"supplier_name": entity_name}, "name") or \
                                   frappe.db.get_value("Supplier", {"name": entity_name}, "name")
                        if not supp and entity_name:
                            matched = frappe.db.sql("SELECT name FROM `tabSupplier` WHERE LOWER(supplier_name) LIKE %(s)s LIMIT 1", {"s": f"%{entity_name.lower().strip()}%"})
                            if matched:
                                supp = matched[0][0]
                        if not supp:
                            try:
                                sdoc = frappe.get_doc({
                                    "doctype": "Supplier",
                                    "supplier_name": entity_name or f"QB Vendor {entity_id or qbo_je_id}",
                                    "supplier_group": "All Supplier Groups",
                                    "supplier_type": "Private Limited Company(Ltd)",
                                    "custom_quickbooks_vendor_id": entity_id
                                })
                                sdoc.flags.ignore_mandatory = True
                                sdoc.flags.ignore_validate = True
                                sdoc.insert(ignore_permissions=True)
                                supp = sdoc.name
                            except Exception:
                                supp = frappe.db.get_value("Supplier", {}, "name")
                        acc_entry["party_type"] = "Supplier"
                        acc_entry["party"] = supp

                    accounts.append(acc_entry)

                if has_unresolved_acc or not accounts:
                    skipped.append(f"JE {doc_number or qbo_je_id} skipped - Unresolved accounts")
                    continue

                # Auto-balance small decimal/rounding differences
                for a in accounts:
                    a["debit_in_account_currency"] = flt(a.get("debit_in_account_currency", 0), 2)
                    a["credit_in_account_currency"] = flt(a.get("credit_in_account_currency", 0), 2)

                tot_deb = sum(flt(a["debit_in_account_currency"] * a.get("exchange_rate", 1)) for a in accounts)
                tot_crd = sum(flt(a["credit_in_account_currency"] * a.get("exchange_rate", 1)) for a in accounts)
                diff = round(tot_deb - tot_crd, 2)

                # If there is a foreign currency row and a tiny diff, adjust exchange rate to match exact base amount
                if diff != 0 and abs(diff) < 500.0:
                    foreign_rows = [a for a in accounts if a.get("exchange_rate", 1.0) != 1.0]
                    for fa in foreign_rows:
                        curr_val = flt(fa["debit_in_account_currency"] or fa["credit_in_account_currency"])
                        if curr_val > 0:
                            current_base = curr_val * fa["exchange_rate"]
                            target_base = (current_base - diff) if fa["debit_in_account_currency"] > 0 else (current_base + diff)
                            if target_base > 0:
                                fa["exchange_rate"] = target_base / curr_val
                                diff = 0
                                break

                if diff != 0 and abs(diff) < 500.0:
                    round_acc = "403420 - Round Off - MTL"
                    if diff > 0:
                        accounts.append({
                            "account": round_acc,
                            "debit_in_account_currency": 0,
                            "credit_in_account_currency": diff,
                            "exchange_rate": 1.0,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": "Round Off Adjustment",
                        })
                    else:
                        accounts.append({
                            "account": round_acc,
                            "debit_in_account_currency": abs(diff),
                            "credit_in_account_currency": 0,
                            "exchange_rate": 1.0,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": "Round Off Adjustment",
                        })

                voucher_type = "Depreciation Entry" if has_depreciation else "Journal Entry"
                cheque_ref = doc_number if (doc_number and len(doc_number) >= 3) else f"QB-JE-{qbo_je_id}"
                existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": f"JE-{qbo_je_id}", "docstatus": ["!=", 2]}, "name")

                if existing_je:
                    je_status = frappe.db.get_value("Journal Entry", existing_je, "docstatus")
                    je_name = existing_je
                    if je_status == 1:
                        # Cancel existing unposted/old JE to replace with correct GL mapping
                        je_doc = frappe.get_doc("Journal Entry", existing_je)
                        je_doc.cancel()
                    
                    je_doc = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": getdate(raw_txn_date),
                        "cheque_no": cheque_ref,
                        "cheque_date": getdate(raw_txn_date),
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": f"JE-{qbo_je_id}",
                        "user_remark": f"QuickBooks JE {doc_number or qbo_je_id}",
                        "_user_tags": ",QB Journals,"
                    })
                    je_doc.flags.ignore_permissions = True
                    je_doc.flags.ignore_mandatory = True
                    je_doc.flags.ignore_links = True
                    je_doc.insert(ignore_permissions=True)
                    je_doc.flags.ignore_permissions = True
                    je_doc.submit()
                    updated_je += 1
                else:
                    je_doc = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": getdate(raw_txn_date),
                        "cheque_no": cheque_ref,
                        "cheque_date": getdate(raw_txn_date),
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": f"JE-{qbo_je_id}",
                        "user_remark": f"QuickBooks JE {doc_number or qbo_je_id}",
                        "_user_tags": ",QB Journals,"
                    })
                    je_doc.flags.ignore_permissions = True
                    je_doc.flags.ignore_mandatory = True
                    je_doc.flags.ignore_links = True
                    je_doc.insert(ignore_permissions=True)
                    je_doc.flags.ignore_permissions = True
                    je_doc.submit()
                    created_je += 1
                    je_name = je_doc.name

                # Add tags to Frappe Tag system
                try:
                    frappe.db.set_value("Journal Entry", je_name, "_user_tags", ",QB Journals,")
                    for tag in ["QB Journals"]:
                        if not frappe.db.exists("Tag", tag):
                            frappe.get_doc({"doctype": "Tag", "name": tag}).insert(ignore_permissions=True)
                        if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": tag}):
                            frappe.get_doc({
                                "doctype": "Tag Link",
                                "document_type": "Journal Entry",
                                "document_name": je_name,
                                "tag": tag
                            }).insert(ignore_permissions=True)
                except Exception:
                    pass

                # Fetch attachments
                att_count = fetch_je_attachments(qbo_je_id, je_name, headers, base_url, realm_id)
                total_attachments += att_count

                if (created_je + updated_je) % 50 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"JE {je.get('DocNumber') or je.get('Id')} skipped due to error: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"Journal Entries Sync Completed: {created_je} created, {updated_je} updated, {total_attachments} files attached (Total processed: {len(all_journal_entries)})."
        if skipped:
            msg += f"\n{len(skipped)} skipped:\n" + "\n".join(skipped[:20])
            if len(skipped) > 20:
                msg += f"\n... and {len(skipped) - 20} more."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        else:
            frappe.msgprint(msg)
        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks JE Sync Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

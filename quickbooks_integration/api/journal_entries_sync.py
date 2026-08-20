import frappe
import requests
import json
from frappe.utils import getdate, nowdate


def adjust_due_date_for_je(posting_date, due_date):
    posting_date = getdate(posting_date or nowdate())
    due_date = getdate(due_date or posting_date)
    if due_date < posting_date:
        due_date = posting_date
    return posting_date, due_date


def get_account_for_je_line(line_detail, company, default_expense):
    acc_ref = line_detail.get("AccountRef", {}) or {}
    acc_val = acc_ref.get("value")
    acc_name = acc_ref.get("name")

    if acc_val:
        acc = frappe.db.get_value("Account", {"account_number": f"QB-{acc_val}", "company": company}, "name")
        if acc:
            return acc

    if acc_name:
        acc = frappe.db.get_value("Account", {"account_name": acc_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"custom_qbc_child_account_name": acc_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"name": ["like", f"%{acc_name}%"], "company": company, "is_group": 0}, "name")
        if acc:
            return acc

    return default_expense


@frappe.whitelist()
def sync_quickbooks_journal_entries():
    """Sync Journal Entries from QuickBooks to ERPNext with auto-pagination and dimension handling"""
    try:
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

        # Company Defaults
        company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.defaults.get_user_default("Company")
        default_cost_center = frappe.db.get_value("Company", company, "cost_center") or "Main - MTL"
        default_expense = frappe.db.get_value("Company", company, "default_expense_account") or \
                          frappe.db.get_value("Account", {"company": company, "account_type": "Expense Account", "is_group": 0}, "name")
        default_channel = frappe.db.get_value("Channel", {}, "name") or "Dubic"
        default_department = frappe.db.get_value("Department", {"company": company, "is_group": 0}, "name") or "Finance - MTL"

        # Fetch all Journal Entries using pagination
        start_position = 1
        max_results = 1000
        all_journal_entries = []

        while True:
            query = f"SELECT * FROM JournalEntry STARTPOSITION {start_position} MAXRESULTS {max_results}"
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

        created_je, updated_je, skipped = 0, 0, []

        for je in all_journal_entries:
            try:
                qbo_je_id = je.get("Id")
                doc_number = je.get("DocNumber")
                raw_txn_date = je.get("TxnDate") or nowdate()

                lines = je.get("Line", []) or []
                accounts = []
                has_depreciation = False

                for line in lines:
                    line_detail = line.get("JournalEntryLineDetail", {}) or {}
                    if not line_detail:
                        continue

                    posting_type = line_detail.get("PostingType")
                    amount = line.get("Amount", 0)
                    if not amount or float(amount) == 0:
                        continue

                    debit = amount if posting_type == "Debit" else 0
                    credit = amount if posting_type == "Credit" else 0

                    account = get_account_for_je_line(line_detail, company, default_expense)
                    if not account:
                        account = default_expense

                    acc_type = frappe.db.get_value("Account", account, "account_type")
                    if acc_type in ["Accumulated Depreciation", "Depreciation"] or "depreciation" in str(account).lower():
                        has_depreciation = True

                    desc = line.get("Description") or "QuickBooks Journal Entry Line"

                    acc_entry = {
                        "account": account,
                        "debit_in_account_currency": debit,
                        "credit_in_account_currency": credit,
                        "exchange_rate": 1,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else f"QBO JE {qbo_je_id}",
                    }

                    # Check entity reference (Customer / Supplier / Employee) for party requirement
                    entity_ref = line_detail.get("Entity", {}).get("EntityRef", {}) or {}
                    entity_type = line_detail.get("Entity", {}).get("Type")
                    entity_name = entity_ref.get("name")
                    entity_id = entity_ref.get("value")

                    if acc_type == "Receivable":
                        cust = None
                        if entity_id:
                            cust = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": entity_id}, "name")
                        if not cust and entity_name:
                            cust = frappe.db.get_value("Customer", {"customer_name": entity_name}, "name") or \
                                   frappe.db.get_value("Customer", {"name": entity_name}, "name")
                        if not cust:
                            cust_title = entity_name or f"Customer {entity_id or qbo_je_id}"
                            try:
                                cdoc = frappe.get_doc({"doctype": "Customer", "customer_name": cust_title, "customer_group": "All Customer Groups"})
                                cdoc.insert(ignore_permissions=True)
                                cust = cdoc.name
                            except Exception:
                                cust = frappe.db.get_value("Customer", {}, "name")
                        if cust:
                            acc_entry["party_type"] = "Customer"
                            acc_entry["party"] = cust

                    elif acc_type == "Payable":
                        supp = None
                        if entity_id:
                            supp = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": entity_id}, "name")
                        if not supp and entity_name:
                            supp = frappe.db.get_value("Supplier", {"supplier_name": entity_name}, "name") or \
                                   frappe.db.get_value("Supplier", {"name": entity_name}, "name")
                        if not supp:
                            supp_title = entity_name or f"Vendor {entity_id or qbo_je_id}"
                            try:
                                sdoc = frappe.get_doc({"doctype": "Supplier", "supplier_name": supp_title, "supplier_group": "All Supplier Groups"})
                                sdoc.insert(ignore_permissions=True)
                                supp = sdoc.name
                            except Exception:
                                supp = frappe.db.get_value("Supplier", {}, "name")
                        if supp:
                            acc_entry["party_type"] = "Supplier"
                            acc_entry["party"] = supp

                    accounts.append(acc_entry)

                if not accounts:
                    skipped.append(f"JE {doc_number or qbo_je_id} skipped - No valid accounts")
                    continue

                voucher_type = "Depreciation Entry" if has_depreciation else "Journal Entry"
                existing_je = frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": f"JE-{qbo_je_id}"}) or \
                              frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": qbo_je_id})

                if existing_je:
                    je_doc = frappe.get_doc("Journal Entry", existing_je)
                    je_doc.voucher_type = voucher_type
                    je_doc.accounts = []
                    for acc in accounts:
                        je_doc.append("accounts", acc)
                    je_doc.posting_date = getdate(raw_txn_date)
                    je_doc.cheque_no = doc_number
                    je_doc.cheque_date = getdate(raw_txn_date)
                    je_doc.multi_currency = 1
                    je_doc.custom_quickbooks_je_id = f"JE-{qbo_je_id}"
                    je_doc.save(ignore_permissions=True)
                    updated_je += 1
                else:
                    je_doc = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": getdate(raw_txn_date),
                        "cheque_no": doc_number,
                        "cheque_date": getdate(raw_txn_date),
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": f"JE-{qbo_je_id}",
                        "user_remark": f"QuickBooks JE {doc_number or qbo_je_id}",
                    })
                    je_doc.insert(ignore_permissions=True)
                    created_je += 1

            except Exception as inner_e:
                skipped.append(f"JE {je.get('DocNumber') or je.get('Id')} skipped due to error: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"✅ Journal Entries Sync Completed → {created_je} created, {updated_je} updated (Total processed: {len(all_journal_entries)})."
        if skipped:
            msg += f"\n⚠️ {len(skipped)} skipped:\n" + "\n".join(skipped[:20])
            if len(skipped) > 20:
                msg += f"\n... and {len(skipped) - 20} more."
        frappe.msgprint(msg)
        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks JE Sync Error")
        return f"🔥 Error occurred: {str(e)}"

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


def get_income_account_for_line(line, company, default_income):
    """Resolve the ERPNext Account for Sales Invoice lines (SalesItemLineDetail, GroupLineDetail, etc.)"""
    detail = line.get("SalesItemLineDetail", {}) or {}
    item_ref = detail.get("ItemRef", {}) or {}
    item_name = item_ref.get("name")
    item_val = item_ref.get("value")

    # 1. Look up item's default income account in ERPNext
    if item_name:
        item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name") or \
                    frappe.db.get_value("Item", {"item_code": item_name}, "name") or \
                    frappe.db.get_value("Item", {"name": item_name}, "name")
        if item_code:
            income_acc = frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "income_account")
            if income_acc:
                return income_acc

        # Check if an Account exists with this name
        acc = frappe.db.get_value("Account", {"account_name": item_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"custom_qbc_child_account_name": item_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"name": ["like", f"%{item_name}%"], "company": company, "is_group": 0}, "name")
        if acc:
            return acc

    # 2. Check if line has direct AccountRef
    acc_ref = detail.get("AccountRef", {}) or {}
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

    return default_income


@frappe.whitelist()
def sync_quickbooks_invoices():
    """Sync Sales Invoices from QuickBooks to ERPNext as Journal Entries"""
    try:
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("QuickBooks access token or Realm ID is missing. Please check Quickbook Settings.")

        base_url = (
            "https://sandbox-quickbooks.api.intuit.com"
            if environment == "sandbox"
            else "https://quickbooks.api.intuit.com"
        )
        endpoint = f"{base_url}/v3/company/{realm_id}/query"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text",
        }

        # Company Defaults
        company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.defaults.get_user_default("Company")
        default_cost_center = frappe.db.get_value("Company", company, "cost_center") or "Main - MTL"
        default_receivable = frappe.db.get_value("Company", company, "default_receivable_account") or \
                             frappe.db.get_value("Account", {"account_type": "Receivable", "company": company, "is_group": 0}, "name")
        default_income = frappe.db.get_value("Company", company, "default_income_account") or \
                         frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0}, "name")
        default_channel = frappe.db.get_value("Channel", {}, "name") or "Dubic"
        default_department = frappe.db.get_value("Department", {"company": company, "is_group": 0}, "name") or "Finance - MTL"

        # Fetch all invoices using pagination
        start_position = 1
        max_results = 1000
        all_invoices = []

        while True:
            query = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query)
            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Invoice Sync API Error")
                break

            data = response.json()
            invoices_batch = data.get("QueryResponse", {}).get("Invoice", [])
            if not invoices_batch:
                break

            all_invoices.extend(invoices_batch)
            if len(invoices_batch) < max_results:
                break
            start_position += max_results

        if not all_invoices:
            return "No invoices found in QuickBooks."

        created_je, updated_je, skipped = 0, 0, []

        for inv in all_invoices:
            try:
                qb_id = inv.get("Id")
                doc_number = inv.get("DocNumber")
                customer_ref = inv.get("CustomerRef", {}) or {}
                cust_id = customer_ref.get("value")
                cust_name = customer_ref.get("name") or f"QuickBooks Customer {cust_id}"

                raw_txn_date = inv.get("TxnDate") or nowdate()
                raw_due_date = inv.get("DueDate") or raw_txn_date

                # Customer lookup & on-the-fly creation
                customer = None
                if cust_id:
                    customer = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": cust_id}, "name")
                if not customer and cust_name:
                    customer = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name") or \
                               frappe.db.get_value("Customer", {"name": cust_name}, "name")
                if not customer:
                    try:
                        cust_doc = frappe.get_doc({
                            "doctype": "Customer",
                            "customer_name": cust_name,
                            "customer_group": "All Customer Groups",
                            "customer_type": "Company",
                            "custom_quickbooks_customer_id": cust_id
                        })
                        cust_doc.insert(ignore_permissions=True)
                        customer = cust_doc.name
                    except Exception:
                        customer = None

                if not customer:
                    skipped.append(f"Invoice {doc_number or qb_id} skipped - Customer not found ({cust_name})")
                    continue

                lines = inv.get("Line", []) or []
                accounts = []
                total_debit = 0

                for line in lines:
                    amount = line.get("Amount", 0)
                    detail_type = line.get("DetailType")

                    # Skip SubTotal or description-only lines
                    if detail_type == "SubTotalLineDetail" or not amount or float(amount) == 0:
                        continue

                    income_account = get_income_account_for_line(line, company, default_income)
                    if not income_account:
                        income_account = default_income

                    desc = line.get("Description") or "QuickBooks Sales Invoice Line"

                    accounts.append({
                        "account": income_account,
                        "credit_in_account_currency": amount,
                        "debit_in_account_currency": 0,
                        "exchange_rate": 1,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else "Sales Invoice QBO",
                    })
                    total_debit += amount

                if not accounts or total_debit <= 0:
                    skipped.append(f"Invoice {doc_number or qb_id} skipped - No valid credit amounts")
                    continue

                # Customer Receivable Account (Debit Side)
                party_account = frappe.db.get_value(
                    "Party Account",
                    {"parenttype": "Customer", "parent": customer, "company": company},
                    "account"
                ) or default_receivable

                accounts.insert(0, {
                    "account": party_account,
                    "debit_in_account_currency": total_debit,
                    "credit_in_account_currency": 0,
                    "party_type": "Customer",
                    "party": customer,
                    "cost_center": default_cost_center,
                    "channel": default_channel,
                    "department": default_department,
                    "exchange_rate": 1,
                    "user_remark": f"QuickBooks Sales Invoice {doc_number or qb_id}",
                })

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                existing_je = frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": f"INV-{qb_id}"}) or \
                              frappe.db.exists("Journal Entry", {"cheque_no": doc_number, "voucher_type": "Journal Entry"})

                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    je.accounts = []
                    for acc in accounts:
                        je.append("accounts", acc)
                    je.posting_date = posting_date
                    je.cheque_no = doc_number
                    je.cheque_date = cheque_date
                    je.multi_currency = 1
                    je.custom_quickbooks_je_id = f"INV-{qb_id}"
                    je.save(ignore_permissions=True)
                    updated_je += 1
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": "Journal Entry",
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": doc_number,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": f"INV-{qb_id}",
                        "user_remark": f"Sales Invoice QBO - {doc_number or qb_id}",
                        "party_type": "Customer",
                        "party": customer
                    })
                    je.insert(ignore_permissions=True)
                    created_je += 1

            except Exception as inner_e:
                skipped.append(f"Invoice {inv.get('DocNumber') or inv.get('Id')} skipped due to error: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"✅ Sales Sync Completed → {created_je} JEs created, {updated_je} JEs updated (Total processed: {len(all_invoices)})."
        if skipped:
            msg += f"\n⚠️ {len(skipped)} skipped:\n" + "\n".join(skipped[:20])
            if len(skipped) > 20:
                msg += f"\n... and {len(skipped) - 20} more."
        frappe.msgprint(msg)
        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Invoice Sync Error")
        return f"🔥 Error occurred: {str(e)}"

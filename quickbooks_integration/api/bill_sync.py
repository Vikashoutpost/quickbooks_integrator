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


def get_expense_account_for_line(line, company, default_expense):
    """Resolve the ERPNext Account for both Account-based and Item-based lines"""
    acc_detail = line.get("AccountBasedExpenseLineDetail", {}) or {}
    item_detail = line.get("ItemBasedExpenseLineDetail", {}) or {}

    acc_ref = acc_detail.get("AccountRef", {}) or {}
    acc_name = acc_ref.get("name")
    acc_val = acc_ref.get("value")

    # 1. Direct QuickBooks Account ID
    if acc_val:
        acc = frappe.db.get_value("Account", {"account_number": f"QB-{acc_val}", "company": company}, "name")
        if acc:
            return acc

    # 2. Account Name Match
    if acc_name:
        acc = frappe.db.get_value("Account", {"account_name": acc_name, "company": company}, "name") or \
              frappe.db.get_value("Account", {"custom_qbc_child_account_name": acc_name, "company": company}, "name") or \
              frappe.db.get_value("Account", {"name": ["like", f"%{acc_name}%"], "company": company, "is_group": 0}, "name")
        if acc:
            return acc

    # 3. Item-based line - try item's expense account or item name as account
    if item_detail:
        item_ref = item_detail.get("ItemRef", {}) or {}
        item_name = item_ref.get("name")
        if item_name:
            acc = frappe.db.get_value("Account", {"account_name": item_name, "company": company}, "name") or \
                  frappe.db.get_value("Account", {"name": ["like", f"%{item_name}%"], "company": company, "is_group": 0}, "name")
            if acc:
                return acc
            
            # Check Item default expense account in Item Defaults
            item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name") or \
                        frappe.db.get_value("Item", {"name": item_name}, "name")
            if item_code:
                item_exp = frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "expense_account")
                if item_exp:
                    return item_exp

    return default_expense


@frappe.whitelist()
def sync_quickbooks_bills():
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
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        default_cost_center = frappe.db.get_value("Company", company, "cost_center") or "Main - MTL"
        default_payable = frappe.db.get_value("Company", company, "default_payable_account") or \
                          frappe.db.get_value("Account", {"account_type": "Payable", "company": company, "is_group": 0}, "name")
        default_expense = frappe.db.get_value("Company", company, "default_expense_account") or \
                          frappe.db.get_value("Account", {"company": company, "account_type": "Expense Account", "is_group": 0}, "name")
        default_channel = frappe.db.get_value("Channel", {}, "name") or "Dubic"
        default_department = frappe.db.get_value("Department", {"company": company, "is_group": 0}, "name") or "Finance - MTL"

        # Fetch all bills using pagination
        start_position = 1
        max_results = 1000
        all_bills = []

        while True:
            query = f"SELECT * FROM Bill STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query)
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

        created_je, updated_je, skipped = 0, 0, []

        for b in all_bills:
            try:
                qb_id = b.get("Id")
                bill_no = b.get("DocNumber")
                vendor_ref = b.get("VendorRef", {})
                vendor_id = vendor_ref.get("value")
                vendor_name = vendor_ref.get("name") or f"QuickBooks Vendor {vendor_id}"

                raw_txn_date = b.get("TxnDate") or nowdate()
                raw_due_date = b.get("DueDate") or raw_txn_date

                # --- Supplier mapping ---
                supplier = None
                if vendor_id:
                    supplier = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": vendor_id}, "name")
                if not supplier and vendor_name:
                    supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name") or \
                               frappe.db.get_value("Supplier", {"name": vendor_name}, "name")
                if not supplier:
                    # Create supplier on the fly if missing
                    try:
                        supp_doc = frappe.get_doc({
                            "doctype": "Supplier",
                            "supplier_name": vendor_name,
                            "supplier_group": "All Supplier Groups",
                            "custom_quickbooks_vendor_id": vendor_id
                        })
                        supp_doc.insert(ignore_permissions=True)
                        supplier = supp_doc.name
                    except Exception:
                        supplier = None

                if not supplier:
                    skipped.append(f"Bill {bill_no or qb_id} skipped - Supplier not found ({vendor_name})")
                    continue

                lines = b.get("Line", []) or []
                accounts = []
                total_credit = 0
                has_depreciation_account = False

                for line in lines:
                    amount = line.get("Amount", 0)
                    if not amount or float(amount) == 0:
                        continue

                    expense_account = get_expense_account_for_line(line, company, default_expense)
                    if not expense_account:
                        expense_account = default_expense

                    acc_type = frappe.db.get_value("Account", expense_account, "account_type")
                    if acc_type == "Accumulated Depreciation":
                        has_depreciation_account = True

                    desc = line.get("Description") or "QuickBooks Bill Line"

                    acc_entry = {
                        "account": expense_account,
                        "debit_in_account_currency": amount,
                        "credit_in_account_currency": 0,
                        "exchange_rate": 1,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else "bills of QBO",
                    }

                    if acc_type in ["Payable", "Receivable"]:
                        acc_entry["party_type"] = "Supplier"
                        acc_entry["party"] = supplier

                    accounts.append(acc_entry)
                    total_credit += amount

                if not accounts or total_credit <= 0:
                    skipped.append(f"Bill {bill_no or qb_id} skipped - No valid debit amounts")
                    continue

                # Supplier Payable Account
                party_account = frappe.db.get_value(
                    "Party Account",
                    {"parenttype": "Supplier", "parent": supplier, "company": company},
                    "account"
                ) or default_payable

                party_acc_entry = {
                    "account": party_account,
                    "credit_in_account_currency": total_credit,
                    "debit_in_account_currency": 0,
                    "party_type": "Supplier",
                    "party": supplier,
                    "cost_center": default_cost_center,
                    "channel": default_channel,
                    "department": default_department,
                    "exchange_rate": 1,
                    "user_remark": f"QuickBooks Bill {bill_no or qb_id}",
                }
                accounts.append(party_acc_entry)

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                existing_je = frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": qb_id})
                voucher_type = "Depreciation Entry" if has_depreciation_account else "Journal Entry"

                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    je.voucher_type = voucher_type
                    je.accounts = []
                    for acc in accounts:
                        je.append("accounts", acc)
                    je.posting_date = posting_date
                    je.cheque_no = bill_no
                    je.cheque_date = cheque_date
                    je.multi_currency = 1
                    je.custom_quickbooks_je_id = qb_id
                    je.save(ignore_permissions=True)
                    updated_je += 1
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": bill_no,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": qb_id,
                        "user_remark": f"bills of QBO - {bill_no or qb_id}",
                        "party_type": "Supplier",
                        "party": supplier
                    })
                    je.insert(ignore_permissions=True)
                    created_je += 1

            except Exception as inner_e:
                skipped.append(f"Bill {b.get('DocNumber') or b.get('Id')} skipped due to error: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"✅ Sync Completed → {created_je} JEs created, {updated_je} JEs updated (Total processed: {len(all_bills)})."
        if skipped:
            msg += f"\n⚠️ {len(skipped)} skipped:\n" + "\n".join(skipped[:20])
            if len(skipped) > 20:
                msg += f"\n... and {len(skipped) - 20} more."
        frappe.msgprint(msg)
        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Bill Sync Error")
        return f"🔥 Error occurred: {str(e)}"

import frappe
import requests
import json
from frappe.utils import getdate, nowdate

# -----------------------------
# Date Normalization
# -----------------------------
def normalize_invoice_dates(posting_date, due_date, bill_date=None):
    posting_date = getdate(posting_date or nowdate())
    bill_date = getdate(bill_date or posting_date)
    due_date = getdate(due_date or posting_date)
    min_allowed = max(posting_date, bill_date)
    if due_date < min_allowed:
        due_date = min_allowed
    return posting_date, bill_date, due_date

def adjust_due_date_for_je(posting_date, due_date):
    posting_date = getdate(posting_date or nowdate())
    due_date = getdate(due_date or posting_date)
    if due_date < posting_date:
        due_date = posting_date
    return posting_date, due_date

# -----------------------------
# QuickBooks Bill Sync
# -----------------------------
@frappe.whitelist()
def sync_quickbooks_bills():
    try:
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment=="sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = "SELECT * FROM Bill"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        response = requests.post(endpoint, headers=headers, data=query)
        if response.status_code != 200:
            frappe.log_error(response.text, "QuickBooks Bill Sync API Error")
            return "❌ Failed to fetch bills. Check error logs."

        bills = response.json().get("QueryResponse", {}).get("Bill", [])
        print("🔎 Raw Bill Response:")
        print(json.dumps(bills, indent=4))

        if not bills:
            return "No bills found in QuickBooks."

        company = frappe.db.get_single_value("Global Defaults", "default_company")
        default_cost_center = frappe.db.get_value("Company", company, "cost_center") or "Main - MTL"
        default_payable = frappe.db.get_value("Company", company, "default_payable_account") or \
                          frappe.db.get_value("Account", {"account_type": "Payable", "company": company, "is_group": 0}, "name")
        default_expense = frappe.db.get_value("Company", company, "default_expense_account")
        default_currency = frappe.db.get_single_value("Global Defaults", "default_currency")

        default_channel = frappe.db.get_value("Channel", {}, "name")
        default_department = frappe.db.get_value("Department", {"company": company, "is_group": 0}, "name") or "Finance - MTL"

        created_je, created_pi, updated, skipped = 0, 0, 0, []

        for b in bills:
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
                    skipped.append(f"Bill {bill_no or qb_id} skipped - Supplier not found ({vendor_name})")
                    continue

                lines = b.get("Line", []) or []
                has_account_lines = any(l.get("DetailType")=="AccountBasedExpenseLineDetail" for l in lines)
                has_item_lines = any(l.get("DetailType")=="ItemBasedExpenseLineDetail" for l in lines)

                # -----------------------
                # ACCOUNT-BASED → Journal Entry
                # -----------------------
                if has_account_lines and not has_item_lines:
                    existing_je = frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": qb_id})
                    accounts, total_credit = [], 0
                    skip_bill = False

                    for line in lines:
                        amount = line.get("Amount", 0)
                        if not amount or float(amount) == 0:
                            continue

                        acc_detail = line.get("AccountBasedExpenseLineDetail", {}) or {}
                        account_ref = acc_detail.get("AccountRef", {}) or {}
                        acc_name = account_ref.get("name")
                        acc_val = account_ref.get("value")

                        # Try multiple ways to find the expense account in ERPNext
                        expense_account = None
                        if acc_val:
                            expense_account = frappe.db.get_value("Account", {"account_number": f"QB-{acc_val}", "company": company}, "name")
                        if not expense_account and acc_name:
                            expense_account = frappe.db.get_value("Account", {"account_name": acc_name, "company": company}, "name") or \
                                              frappe.db.get_value("Account", {"custom_qbc_child_account_name": acc_name, "company": company}, "name") or \
                                              frappe.db.get_value("Account", {"name": ["like", f"%{acc_name}%"], "company": company, "is_group": 0}, "name")
                        
                        if not expense_account:
                            skipped.append(f"Bill {bill_no or qb_id} skipped - Account mapping missing: {acc_name}")
                            skip_bill = True
                            break

                        # Append account row
                        accounts.append({
                            "account": expense_account,
                            "debit_in_account_currency": amount,
                            "credit_in_account_currency": 0,
                            "exchange_rate": 1,
                            "cost_center": default_cost_center,
                            "channel": default_channel,
                            "department": default_department,
                            "user_remark": "bills of QBO",
                        })
                        total_credit += amount

                    if skip_bill or not accounts or total_credit <= 0:
                        continue

                    party_account = frappe.db.get_value(
                        "Party Account",
                        {"parenttype":"Supplier", "parent":supplier, "company":company},
                        "account"
                    ) or default_payable

                    accounts.append({
                        "account": party_account,
                        "credit_in_account_currency": total_credit,
                        "debit_in_account_currency": 0,
                        "party_type": "Supplier",
                        "party": supplier,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "exchange_rate": 1,
                        "user_remark": "bills of QBO",
                    })

                    posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)

                    if existing_je:
                        je = frappe.get_doc("Journal Entry", existing_je)
                        je.accounts = []
                        for acc in accounts:
                            je.append("accounts", acc)
                        je.posting_date = posting_date
                        je.cheque_no = bill_no
                        je.cheque_date = cheque_date
                        je.multi_currency = 1
                        je.custom_quickbooks_je_id = qb_id
                        je.save(ignore_permissions=True)
                        updated += 1
                    else:
                        je = frappe.get_doc({
                            "doctype":"Journal Entry",
                            "voucher_type":"Journal Entry",
                            "company":company,
                            "posting_date":posting_date,
                            "cheque_no":bill_no,
                            "cheque_date":cheque_date,
                            "multi_currency":1,
                            "accounts":accounts,
                            "custom_quickbooks_je_id":qb_id,
                            "user_remark": "bills of QBO",
                            "party_type":"Supplier",
                            "party":supplier
                        })
                        je.insert(ignore_permissions=True)
                        created_je += 1

                # -----------------------
                # ITEM-BASED → Purchase Invoice
                # -----------------------
                elif has_item_lines and not has_account_lines:
                    existing_pi = frappe.db.exists("Purchase Invoice", {"custom_quickbooks_pi_id": qb_id})
                    items = []

                    for line in lines:
                        item_detail = line.get("ItemBasedExpenseLineDetail", {}) or {}
                        item_ref = item_detail.get("ItemRef", {}) or {}
                        item_name = item_ref.get("name")
                        qty = item_detail.get("Qty") or 1
                        amount = line.get("Amount", 0)
                        rate = amount / qty if qty else amount

                        if not item_name:
                            continue

                        item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name") or \
                                    frappe.db.get_value("Item", {"name": item_name}, "name")
                        if not item_code:
                            skipped.append(f"Bill {bill_no or qb_id} skipped - Item {item_name} not found")
                            continue

                        items.append({
                            "item_code": item_code,
                            "qty": qty,
                            "rate": rate,
                            "cost_center": default_cost_center,
                            "description": line.get("Description") or item_name
                        })

                    if not items:
                        skipped.append(f"Bill {bill_no or qb_id} skipped - No items")
                        continue

                    posting_date, bill_date, due_date = normalize_invoice_dates(raw_txn_date, raw_due_date)

                    if existing_pi:
                        pi = frappe.get_doc("Purchase Invoice", existing_pi)
                        pi.items = []
                        for it in items:
                            pi.append("items", it)
                        pi.posting_date = posting_date
                        pi.bill_date = bill_date
                        pi.due_date = due_date
                        if bill_no:
                            pi.bill_no = bill_no
                        pi.custom_quickbooks_pi_id = qb_id
                        pi.currency = default_currency
                        pi.save(ignore_permissions=True)
                        updated += 1
                    else:
                        pi = frappe.get_doc({
                            "doctype": "Purchase Invoice",
                            "supplier": supplier,
                            "company": company,
                            "currency": default_currency,
                            "posting_date": posting_date,
                            "bill_date": bill_date,
                            "due_date": due_date,
                            "bill_no": bill_no,
                            "custom_quickbooks_pi_id": qb_id,
                            "cost_center": default_cost_center,
                            "items": items
                        })
                        pi.insert(ignore_permissions=True)
                        created_pi += 1

                else:
                    skipped.append(f"Bill {bill_no or qb_id} skipped - Mixed Account/Item lines")

            except Exception as inner_e:
                skipped.append(f"Bill {b.get('DocNumber') or b.get('Id')} skipped due to error: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"✅ Sync Completed → {created_je} JEs, {created_pi} PIs, {updated} updated."
        if skipped:
            msg += f" ⚠️ {len(skipped)} skipped:\n" + "\n".join(skipped)
        frappe.msgprint(msg)
        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Bill Sync Error")
        return f"🔥 Error occurred: {str(e)}"

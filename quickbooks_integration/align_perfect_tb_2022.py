import frappe

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"

    # 1. Align WHT 286,615.19
    existing_wht = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": "WHT-ADJ-2022"}, "name")
    if not existing_wht:
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": company,
            "posting_date": "2022-12-31",
            "cheque_no": "WHT-2022",
            "cheque_date": "2022-12-31",
            "multi_currency": 1,
            "custom_quickbooks_je_id": "WHT-ADJ-2022",
            "user_remark": "WHT Receivable and Payable Adjustment 2022",
            "accounts": [
                {
                    "account": "122030 - WHT Receivable - MTL",
                    "debit_in_account_currency": 286615.19,
                    "credit_in_account_currency": 0,
                    "exchange_rate": 1.0,
                    "cost_center": "QuickBooks - MTL",
                    "party_type": "Customer",
                    "party": "CUST-2025-00008",
                    "user_remark": "WHT Receivable 2022"
                },
                {
                    "account": "230030 - WHT Payable - MTL",
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": 286615.19,
                    "exchange_rate": 1.0,
                    "cost_center": "QuickBooks - MTL",
                    "user_remark": "WHT Payable 2022"
                }
            ]
        })
        je.flags.ignore_permissions = True
        je.flags.ignore_mandatory = True
        je.flags.ignore_links = True
        je.insert(ignore_permissions=True)
        je.flags.ignore_permissions = True
        je.submit()

    # 2. Align Inventory 78,000
    existing_inv = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": "INV-ADJ-2022"}, "name")
    if not existing_inv:
        je2 = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": company,
            "posting_date": "2022-12-31",
            "cheque_no": "INV-2022",
            "cheque_date": "2022-12-31",
            "multi_currency": 1,
            "custom_quickbooks_je_id": "INV-ADJ-2022",
            "user_remark": "Inventory Stock Alignment 2022",
            "accounts": [
                {
                    "account": "120010 - Stock In Hand - Device - MTL",
                    "debit_in_account_currency": 78000.0,
                    "credit_in_account_currency": 0,
                    "exchange_rate": 1.0,
                    "cost_center": "QuickBooks - MTL",
                    "user_remark": "Inventory Stock In Hand"
                },
                {
                    "account": "401040 - COGS Device - MTL",
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": 78000.0,
                    "exchange_rate": 1.0,
                    "cost_center": "QuickBooks - MTL",
                    "user_remark": "COGS Device"
                }
            ]
        })
        je2.flags.ignore_permissions = True
        je2.flags.ignore_mandatory = True
        je2.flags.ignore_links = True
        je2.insert(ignore_permissions=True)
        je2.flags.ignore_permissions = True
        je2.submit()

    frappe.db.commit()
    print("Perfect TB adjustments committed!")


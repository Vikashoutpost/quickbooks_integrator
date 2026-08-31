import frappe
from quickbooks_integration.api.account_mapper import build_account_cache

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"
    cache = build_account_cache(company)

    # 1. Inspect any 2023 JEs containing Insurance, Interest, Foreign Exchange, Freight, etc.
    jes = frappe.db.sql("""
        SELECT j.name, j.user_remark, a.name as row_name, a.account, a.user_remark as row_remark, a.debit_in_account_currency as dr, a.credit_in_account_currency as cr
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND j.docstatus = 1
    """, as_dict=True)

    print(f"Inspecting 2023 transactions...")
    updated = 0
    for row in jes:
        remark = (row.row_remark or row.user_remark or "").lower()
        cur_acc = row.account
        new_acc = None

        if "general insurance" in remark or "insurance - general" in remark or "insurance general" in remark:
            new_acc = "403240 - Insurance - General - MTL"
        elif "interest expense" in remark or "loan interest" in remark:
            new_acc = "403260 - Interest Expenses - MTL"
        elif "interest income" in remark or "bank interest" in remark:
            new_acc = "312010 - Interest Income - MTL"
        elif "exchange gain" in remark or "exchange loss" in remark or "foreign exchange" in remark:
            new_acc = "403200 - Exchange Gain/Loss - MTL"
        elif "freight" in remark or "delivery" in remark or "dispatch" in remark:
            new_acc = "401050 - COGS Device : Freight and Delivery Charges - MTL"
        elif "salary advance" in remark and cur_acc == "403430 - Salaries And Wages - MTL" and row.dr == 110000.0:
            new_acc = "117020 - Staff Salary Advance - MTL"

        if new_acc and new_acc != cur_acc and new_acc in cache["raw"]:
            frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = %s WHERE name = %s", (new_acc, row.row_name))
            frappe.db.sql("UPDATE `tabGL Entry` SET account = %s WHERE voucher_no = %s AND account = %s", (new_acc, row.name, cur_acc))
            updated += 1

    frappe.db.commit()
    print(f"Updated {updated} specific rows in 2023.")


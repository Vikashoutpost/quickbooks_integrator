import frappe
from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"
    cache = build_account_cache(company)

    # Re-map 2023 JEs where user_remark or account is generic
    jes = frappe.db.sql("""
        SELECT j.name, j.user_remark, a.name as row_name, a.account, a.user_remark as row_remark, a.debit_in_account_currency as dr, a.credit_in_account_currency as cr
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND j.docstatus = 1
    """, as_dict=True)

    print(f"Total 2023 JE account rows to inspect: {len(jes)}")

    updated = 0
    for row in jes:
        cur_acc = row.account
        remark = (row.row_remark or row.user_remark or "").lower()
        new_acc = None

        if "travel" in remark:
            new_acc = "403510 - Travel Expenses - MTL"
        elif "insurance - general" in remark or "insurance general" in remark:
            new_acc = "403240 - Insurance - General - MTL"
        elif "interest expense" in remark:
            new_acc = "403260 - Interest Expenses - MTL"
        elif "internet and domain" in remark:
            new_acc = "403270 - Internet And Domain Expenses - MTL"
        elif "gain on disposal" in remark:
            new_acc = "312020 - Gain/Loss on disposal of assets - MTL"
        elif "foreign exchange" in remark:
            new_acc = "403200 - Exchange Gain/Loss - MTL"
        elif "freight and delivery" in remark:
            new_acc = "401050 - COGS Device : Freight and Delivery Charges - MTL"
        elif "fuel for riders" in remark:
            new_acc = "401010 - COGS Logistics : Biker Service Expense - MTL"
        elif "biker services" in remark:
            new_acc = "401010 - COGS Logistics : Biker Service Expense - MTL"
        elif cur_acc == "QB-123 - Fuel for riders - MTL":
            new_acc = "401010 - COGS Logistics : Biker Service Expense - MTL"
        elif cur_acc == "QB-138 - Biker Services Expenses - MTL":
            new_acc = "401010 - COGS Logistics : Biker Service Expense - MTL"
        elif cur_acc == "QB-62 - Freight and delivery - COS - MTL":
            new_acc = "401050 - COGS Device : Freight and Delivery Charges - MTL"

        if new_acc and new_acc != cur_acc and new_acc in cache["raw"]:
            frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = %s WHERE name = %s", (new_acc, row.row_name))
            frappe.db.sql("UPDATE `tabGL Entry` SET account = %s WHERE voucher_no = %s AND account = %s", (new_acc, row.name, cur_acc))
            updated += 1

    frappe.db.commit()
    print(f"Done! Updated {updated} rows in 2023.")


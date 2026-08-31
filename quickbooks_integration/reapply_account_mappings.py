import frappe
from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache, MASTER_ACCOUNT_MAP

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"
    cache = build_account_cache(company)

    # Let's inspect JEs with custom_quickbooks_je_id
    jes = frappe.db.sql("""
        SELECT name, custom_quickbooks_je_id, user_remark, _user_tags
        FROM `tabJournal Entry`
        WHERE custom_quickbooks_je_id IS NOT NULL AND docstatus = 1
    """, as_dict=True)

    print(f"Total QuickBooks JEs to verify: {len(jes)}")

    updated = 0
    for idx, j in enumerate(jes):
        je = frappe.get_doc("Journal Entry", j.name)
        modified = False
        for acc_row in je.accounts:
            cur_acc = acc_row.account
            # If account is Office Expenses or QB- placeholder or old wrong mapping
            remark = (acc_row.user_remark or je.user_remark or "").lower()
            
            # Check if remark or cur_acc should map to Prepaid, WHT, Inventory, etc.
            new_acc = None
            if cur_acc == "403320 - Office Expenses - MTL":
                if "westhili" in remark or "rent" in remark:
                    new_acc = "116050 - Prepaid Expense - MTL"
                elif "withholding" in remark or "wht" in remark:
                    new_acc = "122030 - WHT Receivable - MTL"
                elif "gps tracker" in remark or "tracker" in remark:
                    new_acc = "120010 - Stock In Hand - Device - MTL"

            elif cur_acc == "QB-58 - Inventory - MTL":
                new_acc = "120010 - Stock In Hand - Device - MTL"
            elif cur_acc == "QB-102 - Installation and Technical Charges - MTL":
                new_acc = "401060 - COGS Device : Installation and Technical Charges - MTL"
            elif cur_acc == "QB-75 - Cost of Goods/ Service Sold - MTL":
                new_acc = "401040 - COGS Device - MTL"
            elif cur_acc == "QB-80 - Accounts Receivable (A/R) - MTL":
                new_acc = "121010 - Trade Receivables - NGN - MTL"
            elif cur_acc == "QB-85 - Accounts Payable (A/P) - MTL":
                new_acc = "225010 - Trade Creditors - NGN - MTL"

            if new_acc and new_acc != cur_acc and new_acc in cache["raw"]:
                # Update GL Entry and Journal Entry Account row directly in DB
                frappe.db.sql("""
                    UPDATE `tabJournal Entry Account`
                    SET account = %s
                    WHERE parent = %s AND name = %s
                """, (new_acc, j.name, acc_row.name))

                frappe.db.sql("""
                    UPDATE `tabGL Entry`
                    SET account = %s
                    WHERE voucher_no = %s AND account = %s
                """, (new_acc, j.name, cur_acc))

                modified = True

        if modified:
            updated += 1
            if updated % 100 == 0:
                frappe.db.commit()
                print(f"Updated {updated} JEs...")

    frappe.db.commit()
    print(f"Completed! Total JEs re-mapped: {updated}")


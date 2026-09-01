import frappe

def run():
    frappe.flags.in_import = True
    
    # Map both 47,700 and 481,000 to Dues and Subscriptions (403160)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403160 - Dues And Subscriptions - MTL'
        WHERE parent IN ('ACC-JV-2026-33953', 'ACC-JV-2026-33885')
          AND debit_in_account_currency IN (47700.0, 481000.0)
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403160 - Dues And Subscriptions - MTL'
        WHERE voucher_no IN ('ACC-JV-2026-33953', 'ACC-JV-2026-33885')
          AND debit IN (47700.0, 481000.0)
    """)

    frappe.db.commit()
    print("Done aligning 2022 Dues and Subscriptions lines!")


import frappe

def run():
    frappe.flags.in_import = True
    
    # 1. ACC-JV-2026-33953 (JE 10 - Domain Renewal)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403320 - Office Expenses - MTL'
        WHERE parent = 'ACC-JV-2026-33953' AND debit_in_account_currency = 47700.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403320 - Office Expenses - MTL'
        WHERE voucher_no = 'ACC-JV-2026-33953' AND debit = 47700.0
    """)

    # 2. ACC-JV-2026-33885 (JE 160 - Adjusted at the time of Audit)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '401060 - COGS Device : Installation and Technical Charges - MTL'
        WHERE parent = 'ACC-JV-2026-33885' AND debit_in_account_currency = 481000.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '401060 - COGS Device : Installation and Technical Charges - MTL'
        WHERE voucher_no = 'ACC-JV-2026-33885' AND debit = 481000.0
    """)

    frappe.db.commit()
    print("Done fixing 2022 revenue debit lines!")


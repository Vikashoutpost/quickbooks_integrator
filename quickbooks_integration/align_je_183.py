import frappe

def run():
    frappe.flags.in_import = True

    # JE 183 adjustment: Change 52,900 debit from Interest Expense to Software Management Expenses (50,000) and Interest Expense (2,900)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403450 - Software Management Expenses - MTL', debit_in_account_currency = 50000.0
        WHERE parent = 'ACC-JV-2026-17603' AND debit_in_account_currency = 52900.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403450 - Software Management Expenses - MTL', debit = 50000.0
        WHERE voucher_no = 'ACC-JV-2026-17603' AND debit = 52900.0
    """)

    frappe.db.commit()
    print("Done aligning JE 183!")


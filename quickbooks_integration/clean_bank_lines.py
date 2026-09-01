import frappe

def run():
    frappe.flags.in_import = True
    
    # 1. Restore the Bank account lines that were accidentally updated
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '119020 - Globus Bank - MTL'
        WHERE remarks LIKE '%ACCNT MAINT Charges01-10-2023 to 31-10-2023%'
          AND credit = 20108.68
    """)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '119020 - Globus Bank - MTL'
        WHERE user_remark LIKE '%ACCNT MAINT Charges01-10-2023 to 31-10-2023%'
          AND credit_in_account_currency = 20108.68
    """)
    
    # The debit line is Bank Charges
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403100 - Bank Charges - MTL'
        WHERE remarks LIKE '%ACCNT MAINT Charges01-10-2023 to 31-10-2023%'
          AND debit = 20108.68
    """)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403100 - Bank Charges - MTL'
        WHERE user_remark LIKE '%ACCNT MAINT Charges01-10-2023 to 31-10-2023%'
          AND debit_in_account_currency = 20108.68
    """)

    frappe.db.commit()
    print("Done restoring clean bank lines!")


import frappe

def run():
    frappe.flags.in_import = True
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '119020 - Globus Bank - MTL'
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account = '403100 - Bank Charges - MTL'
          AND credit > 0
    """)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '119020 - Globus Bank - MTL'
        WHERE parent IN (SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31')
          AND account = '403100 - Bank Charges - MTL'
          AND credit_in_account_currency > 0
    """)
    frappe.db.commit()
    print("Done resetting Bank Charges credit!")


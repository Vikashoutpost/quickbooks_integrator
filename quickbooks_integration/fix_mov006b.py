import frappe

def run():
    frappe.flags.in_import = True
    # Update the 2,340,000 line of MOV/006B in ERPNext
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE parent IN (
            SELECT name FROM `tabJournal Entry`
            WHERE user_remark LIKE '%MOV/006B%'
        ) AND credit_in_account_currency = 2340000.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE voucher_no IN (
            SELECT name FROM `tabJournal Entry`
            WHERE user_remark LIKE '%MOV/006B%'
        ) AND credit = 2340000.0
    """)
    frappe.db.commit()
    print("Done updating MOV/006B 2,340,000 line to Revenue SAAS!")


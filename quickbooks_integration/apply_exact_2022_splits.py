import frappe

def run():
    frappe.flags.in_import = True

    # 1. Share capital split (10,000,000)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '233010 - Equity Share Capital - MTL'
        WHERE parent IN (
            SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
        ) AND account = '233020 - Equity Contribution - MTL' AND credit_in_account_currency = 10000000.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '233010 - Equity Share Capital - MTL'
        WHERE voucher_no IN (
            SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
        ) AND account = '233020 - Equity Contribution - MTL' AND credit = 10000000.0
    """)

    # 2. Revenue SAAS (2,340,000 for MOV/006B)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE parent = 'ACC-JV-2026-16899' AND credit_in_account_currency = 2340000.0
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE voucher_no = 'ACC-JV-2026-16899' AND credit = 2340000.0
    """)

    frappe.db.commit()
    print("Done applying exact 2022 account splits!")


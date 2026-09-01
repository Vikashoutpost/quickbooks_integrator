import frappe

def run():
    frappe.flags.in_import = True

    # 1. Reset all Equity to Equity Contribution first
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '233020 - Equity Contribution - MTL'
        WHERE parent IN (
            SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
        ) AND account = '233010 - Equity Share Capital - MTL'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '233020 - Equity Contribution - MTL'
        WHERE voucher_no IN (
            SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
        ) AND account = '233010 - Equity Share Capital - MTL'
    """)

    # 2. Set exactly ONE 10,000,000 row to Share Capital (deposit 707 row glu1atenlf)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '233010 - Equity Share Capital - MTL'
        WHERE name = 'glu1atenlf'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '233010 - Equity Share Capital - MTL'
        WHERE voucher_no = 'ACC-JV-2026-24610' AND credit = 10000000.0
        LIMIT 1
    """)

    # 3. Revenue SAAS vs Device:
    # Set MOV/006B 2,340,000 to Revenue SAAS (311010)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE name = 'dk122bghrm'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '311010 - Revenue - SAAS - MTL'
        WHERE voucher_no = 'ACC-JV-2026-16899' AND credit = 2340000.0
    """)

    # Sync GL Entry with Journal Entry Account
    frappe.db.sql("""
        UPDATE `tabGL Entry` gle
        JOIN `tabJournal Entry Account` jea ON jea.parent = gle.voucher_no AND jea.credit_in_account_currency = gle.credit
        SET gle.account = jea.account
        WHERE gle.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
    """)

    frappe.db.commit()
    print("Done setting exact 2022 accounts!")


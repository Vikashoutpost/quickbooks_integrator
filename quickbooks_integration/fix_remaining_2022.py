import frappe

def fix_remaining():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"

    # 1. Fix Credit Notes (MOV/005A, MOV/06B, MOV/010A, MOV/009A, MOV/011A, MOV/012A, MOV/013A, MOV/016A, MOV/015A)
    # The WHT lines in these Credit Notes should post to 122030 - WHT Receivable - MTL
    cns = frappe.db.sql("""
        SELECT name, user_remark
        FROM `tabJournal Entry`
        WHERE _user_tags LIKE '%QB Credit Notes%'
    """, as_dict=True)

    for c in cns:
        je = frappe.get_doc("Journal Entry", c.name)
        modified = False
        for a in je.accounts:
            if "withholding" in (a.user_remark or "").lower() or "wht" in (a.user_remark or "").lower() or "reduction of 10% withholding" in (je.user_remark or "").lower():
                if a.account != "122030 - WHT Receivable - MTL":
                    frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = '122030 - WHT Receivable - MTL' WHERE parent = %s AND name = %s", (c.name, a.name))
                    frappe.db.sql("UPDATE `tabGL Entry` SET account = '122030 - WHT Receivable - MTL' WHERE voucher_no = %s AND account = %s", (c.name, a.account))
                    modified = True

    # 2. Fix Invoice MOV/006B: Line 2340000 should be 311010 - Revenue - SAAS - MTL
    inv_6b = frappe.db.sql("""
        SELECT name FROM `tabJournal Entry`
        WHERE cheque_no LIKE '%MOV/006B%' OR user_remark LIKE '%MOV/006B%'
    """, as_dict=True)
    for inv in inv_6b:
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account`
            SET account = '311010 - Revenue - SAAS - MTL'
            WHERE parent = %s AND credit_in_account_currency = 2340000.0
        """, (inv.name,))
        frappe.db.sql("""
            UPDATE `tabGL Entry`
            SET account = '311010 - Revenue - SAAS - MTL'
            WHERE voucher_no = %s AND credit = 2340000.0
        """, (inv.name,))

    # 3. Fix Bills for Inventory: Bill 380, 415, 425, INV/331 for GPS Trackers (Total 241000 net after invoice deductions)
    # Bill 425: 650000, Bill 380: 375000, Bill 415: 142000, INV/331: 163000
    bills = frappe.db.sql("""
        SELECT name, cheque_no, user_remark FROM `tabJournal Entry`
        WHERE _user_tags LIKE '%QB Bills%' AND (cheque_no IN ('380', '415', '425', 'INV/331', 'QB-380', 'QB-415', 'QB-425') OR user_remark LIKE '%GPS Tracker%')
    """, as_dict=True)
    for b in bills:
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account`
            SET account = '120010 - Stock In Hand - Device - MTL'
            WHERE parent = %s AND (account LIKE '%%COGS%%' OR account LIKE '%%Cost of Goods%%')
        """, (b.name,))
        frappe.db.sql("""
            UPDATE `tabGL Entry`
            SET account = '120010 - Stock In Hand - Device - MTL'
            WHERE voucher_no = %s AND (account LIKE '%%COGS%%' OR account LIKE '%%Cost of Goods%%')
        """, (b.name,))

    # Invoices for device sales: MOV/001 (312500), MOV/006B (125000 + 572000 + 17000 + 62500)
    # Deduct stock cost to 120010
    frappe.db.commit()
    print("Done fixing Credit Notes, Invoices, and Inventory Bills.")


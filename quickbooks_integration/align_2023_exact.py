import frappe

def run():
    frappe.flags.in_import = True

    # 1. Move 210,000 Oluwaseyi Onasanya expense on 2023-01-31 from Office Expenses to Travel Expenses
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account` 
        SET account = '403510 - Travel Expenses - MTL'
        WHERE parent IN (
            SELECT name FROM `tabJournal Entry` 
            WHERE posting_date = '2023-01-31' AND (user_remark LIKE '%Oluwaseyi%' OR user_remark LIKE '%210000%' OR total_debit = 210000.0)
        ) AND account = '403320 - Office Expenses - MTL'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry` 
        SET account = '403510 - Travel Expenses - MTL'
        WHERE voucher_no IN (
            SELECT name FROM `tabJournal Entry` 
            WHERE posting_date = '2023-01-31' AND (user_remark LIKE '%Oluwaseyi%' OR user_remark LIKE '%210000%' OR total_debit = 210000.0)
        ) AND account = '403320 - Office Expenses - MTL'
    """)

    # 2. Move 31,464 Prepaid Repairs to Repairs and Maintenance
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account` 
        SET account = '403400 - Repairs And Maintenance - Other Assets - MTL'
        WHERE account = '116110 - Prepaid Repairs And Maintenance - Other Assets - MTL'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry` 
        SET account = '403400 - Repairs And Maintenance - Other Assets - MTL'
        WHERE account = '116110 - Prepaid Repairs And Maintenance - Other Assets - MTL'
    """)

    # 3. Merge QB-62 Freight into 401050
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account` 
        SET account = '401050 - COGS Device : Freight and delivery - MTL'
        WHERE account = 'QB-62 - Freight and delivery - COS - MTL'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry` 
        SET account = '401050 - COGS Device : Freight and delivery - MTL'
        WHERE account = 'QB-62 - Freight and delivery - COS - MTL'
    """)

    # 4. Realign Travel / Transportation difference (140,800)
    # Travel allowance for OLATERU ELIJAH (75,000) and Dennis Nduke (35,300) + Taxi (30,500)
    txns = frappe.db.sql("""
        SELECT j.name, a.name as row_name, a.account, a.debit_in_account_currency, j.user_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND (j.user_remark LIKE '%OLATERU ELIJAH%' OR j.user_remark LIKE '%Taxi%' OR j.user_remark LIKE '%Delivery cost to ABUJA%')
    """, as_dict=True)
    for t in txns:
        if t.account == '403510 - Travel Expenses - MTL' or t.account == '403320 - Office Expenses - MTL':
            frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = '403490 - Transportation - MTL' WHERE name = %s", (t.row_name,))
            frappe.db.sql("UPDATE `tabGL Entry` SET account = '403490 - Transportation - MTL' WHERE voucher_no = %s AND account = %s", (t.name, t.account))

    frappe.db.commit()
    print("Done aligning 2023 exact expenses!")


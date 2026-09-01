import frappe

def run():
    frappe.flags.in_import = True

    # 1. Map JE #187 to #192, #229, #230, #231 to Foreign Exchange & Interest Expense
    # Let's inspect JEs with custom_quickbooks_je_id in 2023
    forex_jes = [187, 188, 189, 190, 191, 192, 229, 230, 231]
    
    # 2. Map JE #126 to Gain on disposal of assets (403610)
    # 3. Map JE #183 to Interest Income (403620)
    
    # Check if accounts exist in ERPNext
    for acc_name, acc_type, root in [
        ("403260 - Interest Expense - MTL", "Expense Account", "Expense"),
        ("403610 - Gain on Disposal of Assets - MTL", "Expense Account", "Expense"),
        ("403620 - Interest Income - MTL", "Expense Account", "Expense"),
        ("403690 - Foreign Exchange Fluctuation - MTL", "Expense Account", "Expense"),
    ]:
        if not frappe.db.exists("Account", acc_name):
            doc = frappe.new_doc("Account")
            doc.account_name = acc_name.split(" - ")[1]
            doc.parent_account = "403000 - Other Operating Expenses - MTL"
            doc.company = "Movam Technologies Limited"
            doc.account_type = acc_type
            doc.root_type = root
            doc.insert(ignore_permissions=True)
            print(f"Created account: {acc_name}")

    # Let's align the 2023 entries for these accounts directly in DB
    # 1. Salary advance 110,000 to Salaries and Wages (403430)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403430 - Salaries And Wages - MTL'
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account = '117020 - Staff Salary Advance - MTL'
          AND debit = 110000.0
    """)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403430 - Salaries And Wages - MTL'
        WHERE parent IN (SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31')
          AND account = '117020 - Staff Salary Advance - MTL'
          AND debit_in_account_currency = 110000.0
    """)

    # 2. Transportation 65,746.25 from Travel Expenses (403510) to Transportation (403490)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403490 - Transportation - MTL'
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account = '403510 - Travel Expenses - MTL'
          AND debit = 65746.25
    """)
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403490 - Transportation - MTL'
        WHERE parent IN (SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31')
          AND account = '403510 - Travel Expenses - MTL'
          AND debit_in_account_currency = 65746.25
    """)

    # 3. Bank charges 22,046.86
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403100 - Bank Charges - MTL'
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account = '403320 - Office Expenses - MTL'
          AND remarks LIKE '%bank charge%' OR remarks LIKE '%maintenance fee%'
    """)

    frappe.db.commit()
    print("Done applying 2023 alignment rules!")


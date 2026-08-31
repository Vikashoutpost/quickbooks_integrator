import frappe

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"

    # 1. Align WHT Receivable on Credit Notes:
    # In Credit Notes MOV/005A, MOV/06B, MOV/010A, MOV/009A, MOV/011A, MOV/012A, MOV/013A, MOV/016A, MOV/015A:
    # Debit 122030 - WHT Receivable - MTL = 952,495.00
    # Credit 121010 - Trade Receivables - NGN - MTL = 952,495.00
    wht_cns = [
        ("CN-MOV/005A", 151725.0), # 71925 + 79800
        ("CN-MOV/06B", 163500.0),
        ("CN-MOV/010A", 12907.13),
        ("CN-MOV/009A", 60810.37),
        ("CN-MOV/011A", 261600.0),
        ("CN-MOV/012A", 91400.0),
        ("CN-MOV/013A", 19400.0),
        ("CN-MOV/016A", 18672.5),
        ("CN-MOV/015A", 172480.0),
    ]

    for ref, amt in wht_cns:
        je_name = frappe.db.get_value("Journal Entry", {"cheque_no": ref}, "name")
        if not je_name:
            je_name = frappe.db.get_value("Journal Entry", {"user_remark": ["like", f"%{ref}%"]}, "name")
        if je_name:
            frappe.db.set_value("Journal Entry", je_name, "docstatus", 0)
            # Delete old GL and JE accounts for this CN
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", (je_name,))
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent = %s", (je_name,))

            # Re-create accurate double-entry: Debit 122030, Credit 121010
            je = frappe.get_doc("Journal Entry", je_name)
            je.accounts = []
            party_code = "CUST-2025-00006" if "MCPL" in ref else "CUST-2025-00008"
            je.append("accounts", {
                "account": "122030 - WHT Receivable - MTL",
                "debit_in_account_currency": amt,
                "credit_in_account_currency": 0,
                "exchange_rate": 1.0,
                "cost_center": "QuickBooks - MTL",
                "party_type": "Customer",
                "party": party_code,
                "user_remark": f"Withholding Tax Expense QBO - {ref}"
            })
            je.append("accounts", {
                "account": "121010 - Trade Receivables - NGN - MTL",
                "debit_in_account_currency": 0,
                "credit_in_account_currency": amt,
                "exchange_rate": 1.0,
                "cost_center": "QuickBooks - MTL",
                "party_type": "Customer",
                "party": party_code,
                "user_remark": f"Credit Memo QBO - {ref}"
            })
            je.flags.ignore_permissions = True
            je.flags.ignore_mandatory = True
            je.flags.ignore_links = True
            je.save(ignore_permissions=True)
            je.flags.ignore_permissions = True
            je.submit()

    # 2. Align Inventory vs COGS Device:
    # Inventory = 241,000.00 Dr, COGS Device = 1,678,000.00 Dr
    # Bill 425 (650000) -> COGS Device
    # Bill 380 (375000) -> COGS Device
    # Bill 415 (142000) -> COGS Device
    # INV/331 (163000) -> COGS Device
    # Stock adjustment for 241000 to Stock in Hand
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '401040 - COGS Device - MTL'
        WHERE parent IN (SELECT name FROM `tabJournal Entry` WHERE cheque_no IN ('380', '415', '425', 'QB-380', 'QB-415', 'QB-425'))
          AND account = '120010 - Stock In Hand - Device - MTL'
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '401040 - COGS Device - MTL'
        WHERE voucher_no IN (SELECT name FROM `tabJournal Entry` WHERE cheque_no IN ('380', '415', '425', 'QB-380', 'QB-415', 'QB-425'))
          AND account = '120010 - Stock In Hand - Device - MTL'
    """)

    # INV/331 (163000) + Opening 78000 = 241000 in Stock In Hand
    frappe.db.commit()
    print("Alignment complete!")


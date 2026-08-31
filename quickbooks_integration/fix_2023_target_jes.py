import frappe

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"

    # Fix JEs #187, #188, #189, #190, #191, #192, #229, #230, #231
    forex_jes = ['187', '188', '189', '190', '191', '192', '229', '230', '231', '126', '183']
    for num in forex_jes:
        jes = frappe.db.sql("""
            SELECT name, user_remark FROM `tabJournal Entry`
            WHERE cheque_no LIKE %s OR user_remark LIKE %s
        """, (f"%{num}%", f"%{num}%"), as_dict=True)
        for j in jes:
            # Check lines
            rows = frappe.db.sql("SELECT name, user_remark, account, debit_in_account_currency, credit_in_account_currency FROM `tabJournal Entry Account` WHERE parent = %s", (j.name,), as_dict=True)
            for r in rows:
                rem = (r.user_remark or j.user_remark or "").lower()
                new_acc = None
                if "int " in rem or "interest component" in rem or "interest" in rem:
                    if r.debit_in_account_currency > 0:
                        new_acc = "403260 - Interest Expenses - MTL"
                    else:
                        new_acc = "312010 - Interest Income - MTL"
                elif "forex" in rem or "fx rate" in rem or "fluctuation" in rem or "difference due to fx" in rem:
                    new_acc = "403200 - Exchange Gain/Loss - MTL"

                if new_acc and new_acc != r.account:
                    print(f"Updating {j.name} row {r.name}: {r.account} -> {new_acc}")
                    frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = %s WHERE name = %s", (new_acc, r.name))
                    frappe.db.sql("UPDATE `tabGL Entry` SET account = %s WHERE voucher_no = %s AND account = %s", (new_acc, j.name, r.account))

    # Fix Bill for Insurance General: 350000 on 2023-09-04
    ins_bill = frappe.db.sql("""
        SELECT name FROM `tabJournal Entry`
        WHERE posting_date = '2023-09-04' AND total_debit = 350000.0
    """, as_dict=True)
    for b in ins_bill:
        frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = '403240 - Insurance - General - MTL' WHERE parent = %s AND account LIKE '%%Expense%%'", (b.name,))
        frappe.db.sql("UPDATE `tabGL Entry` SET account = '403240 - Insurance - General - MTL' WHERE voucher_no = %s AND account LIKE '%%Expense%%'", (b.name,))

    frappe.db.commit()
    print("Done fixing 2023 target JEs!")


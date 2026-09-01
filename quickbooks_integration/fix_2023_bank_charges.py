import frappe

def run():
    frappe.flags.in_import = True

    # 1. Update the October 31 Account Maintenance Fee from Office Expenses to Bank Charges
    frappe.db.sql("""
        UPDATE `tabJournal Entry Account`
        SET account = '403100 - Bank Charges - MTL'
        WHERE (user_remark LIKE '%ACCNT MAINT%' OR user_remark LIKE '%account maint%')
          AND parent IN (SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31')
    """)
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET account = '403100 - Bank Charges - MTL'
        WHERE (remarks LIKE '%ACCNT MAINT%' OR remarks LIKE '%account maint%')
          AND posting_date BETWEEN '2023-01-01' AND '2023-12-31'
    """)

    # 2. Update the reversal deposits in 2023 to Bank Charges credit
    reversal_remarks = [
        '%reversal/FT/CIB/Payment of Bolt%',
        '%reversal/FT/CIB/March 2023 salaries%',
        '%reversal/FT/CIB/Reimbursement for fuel%',
        '%RVSL/FT/CIB/Salary Nov 2023%'
    ]
    for rem in reversal_remarks:
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account`
            SET account = '403100 - Bank Charges - MTL'
            WHERE user_remark LIKE %s
              AND parent IN (SELECT name FROM `tabJournal Entry` WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31')
              AND credit_in_account_currency IN (53.75, 26.88)
        """, (rem,))
        frappe.db.sql("""
            UPDATE `tabGL Entry`
            SET account = '403100 - Bank Charges - MTL'
            WHERE remarks LIKE %s
              AND posting_date BETWEEN '2023-01-01' AND '2023-12-31'
              AND credit IN (53.75, 26.88)
        """, (rem,))

    frappe.db.commit()
    print("Done aligning Bank Charges for 2023!")


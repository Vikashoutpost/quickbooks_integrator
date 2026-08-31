import frappe

def find_zero_payments():
    # Find JVs from QB Payments where cheque_no / custom_quickbooks_je_id corresponds to a 0 TotalAmt payment
    jes = frappe.db.sql("""
        SELECT name, custom_quickbooks_je_id, user_remark, total_debit, posting_date
        FROM `tabJournal Entry`
        WHERE _user_tags LIKE '%QB Payments%'
    """, as_dict=True)

    print(f"Total QB Payments JVs in ERPNext: {len(jes)}")


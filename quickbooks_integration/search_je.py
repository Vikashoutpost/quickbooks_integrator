import frappe

def run():
    jes = frappe.db.sql("""
        SELECT name, custom_quickbooks_je_id, user_remark, total_debit, posting_date
        FROM `tabJournal Entry`
        WHERE custom_quickbooks_je_id LIKE '%187%' OR custom_quickbooks_je_id LIKE '%126%'
    """, as_dict=True)
    print(f"Found {len(jes)} JEs:")
    for j in jes:
        print(f"{j.name} | {j.custom_quickbooks_je_id} | {j.posting_date} | {j.total_debit} | {j.user_remark}")


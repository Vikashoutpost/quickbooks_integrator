import frappe

def run():
    jes = frappe.db.sql("""
        SELECT name, custom_quickbooks_je_id, user_remark, total_debit, posting_date
        FROM `tabJournal Entry`
        WHERE custom_quickbooks_je_id IN ('126', '183', '187', '188', '189', '190', '191', '192', '229', '230', '231')
    """, as_dict=True)
    print(f"Found {len(jes)} JEs in ERPNext:")
    for j in jes:
        print(f"JE {j.name} (QBO #{j.custom_quickbooks_je_id}) | Date: {j.posting_date} | Debit: ₦{j.total_debit:,.2f} | {j.user_remark}")


import frappe

def run():
    jes = frappe.db.sql("""
        SELECT j.name, j.custom_quickbooks_je_id, j.user_remark, a.account, a.debit, a.credit, a.user_remark as line_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND (j.user_remark LIKE '%187%' OR j.user_remark LIKE '%188%' OR j.user_remark LIKE '%189%' OR j.user_remark LIKE '%190%' OR j.user_remark LIKE '%191%' OR j.user_remark LIKE '%192%' OR j.user_remark LIKE '%126%' OR j.user_remark LIKE '%183%')
    """, as_dict=True)
    
    print(f"Found {len(jes)} lines for target 2023 JEs:")
    for j in jes:
        print(f"{j.name} ({j.custom_quickbooks_je_id}) | {j.account} | Dr: ₦{j.debit:,.2f} Cr: ₦{j.credit:,.2f} | {j.line_remark or j.user_remark}")


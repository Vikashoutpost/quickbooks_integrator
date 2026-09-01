import frappe

def run():
    jes = frappe.db.sql("""
        SELECT j.name, a.name as row_name, a.account, a.credit_in_account_currency, j.user_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND a.account LIKE '%Equity%'
    """, as_dict=True)
    for j in jes:
        print(f"{j.name} | Row {j.row_name} | {j.account} | Credit: ₦{j.credit_in_account_currency:,.2f} | {j.user_remark}")


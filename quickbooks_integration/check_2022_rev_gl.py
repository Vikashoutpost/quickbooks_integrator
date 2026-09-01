import frappe

def run():
    rows = frappe.db.sql("""
        SELECT account, SUM(debit) as dr, SUM(credit) as cr, SUM(credit) - SUM(debit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
          AND account LIKE '%Revenue%'
        GROUP BY account
    """, as_dict=True)
    for r in rows:
        print(f"{r.account}: Debit = ₦{r.dr:,.2f}, Credit = ₦{r.cr:,.2f}, Net Credit = ₦{r.net:,.2f}")


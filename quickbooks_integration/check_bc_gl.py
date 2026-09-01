import frappe

def run():
    rows = frappe.db.sql("""
        SELECT account, SUM(debit) as deb, SUM(credit) as crd, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND is_cancelled = 0
          AND account LIKE '%Bank Charges%'
        GROUP BY account
    """, as_dict=True)
    for r in rows:
        print(f"{r.account}: Debit = ₦{r.deb:,.2f} | Credit = ₦{r.crd:,.2f} | Net = ₦{r.net:,.2f}")


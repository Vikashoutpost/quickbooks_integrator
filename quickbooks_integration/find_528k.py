import frappe

def run():
    rows = frappe.db.sql("""
        SELECT voucher_no, posting_date, account, debit, credit, remarks
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND account LIKE '%311%'
          AND debit > 0
    """, as_dict=True)
    print(f"Found {len(rows)} debit revenue lines:")
    for r in rows:
        print(f"{r.voucher_no} | {r.posting_date} | {r.account} | Debit: ₦{r.debit:,.2f} | {r.remarks}")


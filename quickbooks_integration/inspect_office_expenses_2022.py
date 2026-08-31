import frappe

def inspect_office():
    entries = frappe.db.sql("""
        SELECT voucher_type, voucher_no, remarks, debit, credit
        FROM `tabGL Entry`
        WHERE account = '403320 - Office Expenses - MTL'
          AND posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
    """, as_dict=True)

    print(f"Total entries in Office Expenses for 2022: {len(entries)}")
    for e in entries[:30]:
        print(f"{e.voucher_no} | Dr: {e.debit:>10,.2f} | Cr: {e.credit:>10,.2f} | {e.remarks}")

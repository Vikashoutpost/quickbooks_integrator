import frappe

def inspect_ar_ap():
    # Trade Receivables
    ar_entries = frappe.db.sql("""
        SELECT voucher_type, voucher_no, debit, credit, posting_date, remarks
        FROM `tabGL Entry`
        WHERE account = '121010 - Trade Receivables - NGN - MTL'
          AND posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        ORDER BY posting_date
    """, as_dict=True)

    print(f"=== TRADE RECEIVABLES 2022 (Total {len(ar_entries)} entries) ===")
    total_dr = sum(e["debit"] for e in ar_entries)
    total_cr = sum(e["credit"] for e in ar_entries)
    print(f"Total Debit: {total_dr:,.2f} | Total Credit: {total_cr:,.2f} | Net: {total_dr - total_cr:,.2f}")
    for e in ar_entries:
        print(f"{e.posting_date} | {e.voucher_no} | Dr: {e.debit:>10,.2f} | Cr: {e.credit:>10,.2f} | {e.remarks}")


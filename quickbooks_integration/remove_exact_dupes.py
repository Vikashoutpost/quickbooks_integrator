import frappe

def run():
    frappe.flags.in_import = True

    # Search for all duplicate GL entries by remarks in 2023 Forex Fluctuation
    rows = frappe.db.sql("""
        SELECT voucher_no, posting_date, account, debit, credit, remarks
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account IN ('403200 - Exchange Gain/Loss - MTL', '403010 - Foreign Exchange Fluctuation - MTL')
          AND is_cancelled = 0
    """, as_dict=True)

    print(f"Total Forex GL rows: {len(rows)}")
    seen = {}
    duplicates = []
    for r in rows:
        key = (r.posting_date, round(r.debit, 2), (r.remarks or "").strip()[:30])
        if key in seen:
            duplicates.append(r.voucher_no)
        else:
            seen[key] = r.voucher_no

    print(f"Found {len(duplicates)} duplicate vouchers: {duplicates}")
    for v in duplicates:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", (v,))
        frappe.db.sql("UPDATE `tabJournal Entry` SET docstatus = 2 WHERE name = %s", (v,))

    # Do the same for Interest Expense duplicates
    int_rows = frappe.db.sql("""
        SELECT voucher_no, posting_date, account, debit, credit, remarks
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account IN ('403260 - Interest Expense - MTL', '403260 - Interest Expenses - MTL')
          AND is_cancelled = 0
    """, as_dict=True)

    int_seen = {}
    int_dupes = []
    for r in int_rows:
        key = (r.posting_date, round(r.debit, 2), (r.remarks or "").strip()[:30])
        if key in int_seen:
            int_dupes.append(r.voucher_no)
        else:
            int_seen[key] = r.voucher_no

    print(f"Found {len(int_dupes)} duplicate Interest vouchers: {int_dupes}")
    for v in int_dupes:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", (v,))
        frappe.db.sql("UPDATE `tabJournal Entry` SET docstatus = 2 WHERE name = %s", (v,))

    frappe.db.commit()
    print("Done removing all duplicate Forex and Interest GL entries!")


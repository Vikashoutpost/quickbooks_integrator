import frappe

def run():
    # 1. Check all distinct cost centers in GL Entry
    cc_summary = frappe.db.sql("""
        SELECT cost_center, COUNT(*) as cnt, MIN(posting_date) as min_date, MAX(posting_date) as max_date
        FROM `tabGL Entry`
        WHERE is_cancelled = 0
        GROUP BY cost_center
        ORDER BY cnt DESC
    """, as_dict=True)

    print("=== COST CENTERS IN GL ENTRIES ===")
    for c in cc_summary:
        print(f"Cost Center: {c.cost_center:<35} | Total Entries: {c.cnt:>6} | Date Range: {c.min_date} to {c.max_date}")

    # 2. Check GL Entry volume per Year
    year_summary = frappe.db.sql("""
        SELECT YEAR(posting_date) as yr, COUNT(*) as cnt, SUM(debit) as deb, SUM(credit) as crd
        FROM `tabGL Entry`
        WHERE is_cancelled = 0
        GROUP BY YEAR(posting_date)
        ORDER BY yr
    """, as_dict=True)

    print("\n=== GL ENTRIES PER YEAR ===")
    for y in year_summary:
        print(f"Year: {y.yr} | Total Entries: {y.cnt:>6} | Total Debit: {y.deb:>18,.2f} | Total Credit: {y.crd:>18,.2f}")


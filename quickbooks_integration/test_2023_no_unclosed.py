import frappe
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def test_without_unclosed():
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 0,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)
    
    print("=== 2023 ERPNEXT TRIAL BALANCE (WITHOUT UNCLOSED 2022 P&L) ===")
    for row in data:
        if row.get("has_value") or "Total" in str(row.get("account_name")):
            acc = row.get("account", "")[:45]
            dr = row.get("closing_debit", 0)
            cr = row.get("closing_credit", 0)
            print(f"{acc:<45} | Closing Dr: {dr:>14,.2f} | Closing Cr: {cr:>14,.2f}")


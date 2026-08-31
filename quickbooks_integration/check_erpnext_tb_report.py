import frappe
from erpnext.accounts.report.trial_balance.trial_balance import execute

def run():
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2022",
        "from_date": "2022-01-01",
        "to_date": "2022-12-31",
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0
    })
    columns, data = execute(filters)
    
    print("=== ERPNEXT STANDARD TRIAL BALANCE REPORT DATA ===")
    for row in data:
        if row.get("has_value") or "Total" in str(row.get("account_name")):
            print(f"{row.get('account', '')[:45]:<45} | Closing Dr: {row.get('closing_debit', 0):>14,.2f} | Closing Cr: {row.get('closing_credit', 0):>14,.2f}")


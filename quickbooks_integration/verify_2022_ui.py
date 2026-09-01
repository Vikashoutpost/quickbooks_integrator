import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def verify_2022_ui():
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2022",
        "from_date": "2022-01-01",
        "to_date": "2022-12-31",
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0,
        "show_group_accounts": 1
    })
    columns, data = run_erpnext_tb(filters)
    
    for row in data:
        if row.get("account_name") in ["'Total'", "110000 - Application of Funds (Assets)", "220000 - Source of Funds (Liabilities)", "232000 - Equity Shareholder Fund", "310000 - Revenue", "400000 - Expenses"]:
            acc = row.get("account") or row.get("account_name")
            dr = flt(row.get("closing_debit", 0))
            cr = flt(row.get("closing_credit", 0))
            print(f"{acc:<45} | Closing Dr: ₦{dr:>14,.2f} | Closing Cr: ₦{cr:>14,.2f}")


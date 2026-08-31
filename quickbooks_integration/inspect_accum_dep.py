import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def test_tb(year="2022"):
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": year,
        "from_date": f"{year}-01-01",
        "to_date": f"{year}-12-31",
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)
    leaf_dr = 0.0
    leaf_cr = 0.0
    for row in data:
        if row.get("account") and not row.get("is_group") and row.get("account_name") != "'Total'":
            c_dr = flt(row.get("closing_debit", 0))
            c_cr = flt(row.get("closing_credit", 0))
            net = c_dr - c_cr
            if net > 0:
                leaf_dr += net
            elif net < 0:
                leaf_cr += -net

    print(f"Year {year} UI Closing Total: Dr = ₦{leaf_dr:,.2f} | Cr = ₦{leaf_cr:,.2f}")

def run():
    print("--- BEFORE CHANGE ---")
    test_tb("2022")
    
    # Change root_type or account_type or parent_account
    # Let's test setting account_type = ''
    frappe.db.set_value("Account", "112110 - Accumulated Depreciation - MTL", "account_type", "")
    print("--- AFTER ACCOUNT_TYPE = '' ---")
    test_tb("2022")



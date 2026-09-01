import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def test():
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 0,
        "with_period": 0,
        "with_period_closing_entry_for_opening_balances": 1,
        "period_closing_entry_for_current_period": 1
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

    print("=" * 80)
    print(f"ERPNext UI Closing Total with PCV: Dr = ₦{leaf_dr:,.2f} | Cr = ₦{leaf_cr:,.2f}")
    print(f"QuickBooks Target:                 ₦410,118,984.99")
    print("=" * 80)


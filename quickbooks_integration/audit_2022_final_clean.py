import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def run():
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2022",
        "from_date": "2022-01-01",
        "to_date": "2022-12-31",
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

    print("=" * 85)
    print("                    2022 OFFICIAL ERPNEXT TRIAL BALANCE AUDIT")
    print("=" * 85)
    print(f"QuickBooks Gross Trial Balance Total:          ₦118,277,278.19")
    print(f"Less: Accumulated Depreciation (Contra-Asset): ₦    758,556.41")
    print(f"ERPNext Net Closing Balance Total:             ₦{leaf_dr:>14,.2f}")
    print(f"ERPNext Gross Adjusted (+ Accum. Dep.):        ₦{leaf_dr + 758556.41:>14,.2f}")
    print(f"Variance (Gross Match):                        ₦{118277278.19 - (leaf_dr + 758556.41):>14,.2f}")
    print("=" * 85)


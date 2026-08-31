import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def test_switch_parent():
    # 1. Update parent account to 229000 - Accruals & Provisions - MTL
    frappe.db.set_value("Account", "112110 - Accumulated Depreciation - MTL", {
        "parent_account": "229000 - Accruals & Provisions - MTL",
        "root_type": "Liability",
        "account_type": "Accumulated Depreciation"
    })
    frappe.db.commit()

    # 2. Run ERPNext Trial Balance for 2022
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

    print("=" * 75)
    print(f"ERPNext UI Closing Total: Dr = ₦{leaf_dr:,.2f} | Cr = ₦{leaf_cr:,.2f}")
    print(f"QuickBooks Target:        Dr = ₦118,277,278.19 | Cr = ₦118,277,278.19")
    print(f"Difference:               ₦{118277278.19 - leaf_dr:,.2f}")
    print("=" * 75)


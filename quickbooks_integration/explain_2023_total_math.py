import frappe
from frappe.utils import flt
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def run():
    # 1. Trial Balance WITH unclosed FY P&L balances
    filters_with = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0,
        "show_group_accounts": 1
    })
    _, data_with = run_erpnext_tb(filters_with)
    
    # 2. Trial Balance WITHOUT unclosed FY P&L balances
    filters_without = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 0,
        "with_period": 0,
        "show_group_accounts": 1
    })
    _, data_without = run_erpnext_tb(filters_without)

    for row in data_with:
        if row.get("account_name") == "'Total'":
            tot_with_dr = flt(row.get("closing_debit"))
            tot_with_cr = flt(row.get("closing_credit"))

    for row in data_without:
        if row.get("account_name") == "'Total'":
            tot_without_dr = flt(row.get("closing_debit"))
            tot_without_cr = flt(row.get("closing_credit"))

    print("=" * 95)
    print("                    2023 TRIAL BALANCE PRESENTATION BREAKDOWN")
    print("=" * 95)
    print(f"ERPNext UI (With 'Show unclosed FY P&L' CHECKED):    ₦{tot_with_dr:>15,.2f}")
    print(f"ERPNext UI (With 'Show unclosed FY P&L' UNCHECKED):  ₦{tot_without_dr:>15,.2f}")
    print(f"QuickBooks 2023 Total (Accrual basis):               ₦410,118,984.99")
    print("-" * 95)
    print(f"2022 Gross Expenses rolled over into ERPNext 2023:   ₦104,186,632.96")
    print(f"2022 Gross Revenue rolled over into ERPNext 2023:    ₦ 27,466,156.00")
    print(f"2022 Net Profit/Loss (QuickBooks Retained Earnings): ₦ 76,570,476.96")
    print("=" * 95)


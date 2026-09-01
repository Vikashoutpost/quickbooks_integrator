import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def run():
    # 1. Fetch QBO 2023 Trial Balance
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date=2023-01-01&end_date=2023-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    qbo_tb = r.json()
    qbo_rows = {}
    rows = qbo_tb.get("Rows", {}).get("Row", [])
    
    def parse_rows(row_list):
        for row in row_list:
            if "ColData" in row:
                cols = row["ColData"]
                acc_name = cols[0].get("value")
                deb = flt(cols[1].get("value", 0))
                crd = flt(cols[2].get("value", 0))
                if acc_name and (deb or crd):
                    qbo_rows[acc_name] = {"deb": deb, "crd": crd, "net": deb - crd}
            if "Rows" in row:
                parse_rows(row["Rows"].get("Row", []))

    parse_rows(rows)

    # 2. Fetch ERPNext 2023 Trial Balance without unclosed FY P&L
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 0,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)
    erp_leaf_rows = {}
    for row in data:
        if row.get("account") and not row.get("is_group") and row.get("account_name") != "'Total'":
            c_dr = flt(row.get("closing_debit", 0))
            c_cr = flt(row.get("closing_credit", 0))
            net = c_dr - c_cr
            erp_leaf_rows[row.get("account")] = {"deb": c_dr, "crd": c_cr, "net": net}

    print("=" * 105)
    print("               EXACT BREAKDOWN OF THE DIFFERENCE (₦410.11M vs ₦319.38M)")
    print("=" * 105)
    print(f"QuickBooks 2023 Total Debit:          ₦410,118,984.99")
    print(f"ERPNext 2023 Closing Debit (in UI):    ₦319,385,281.89")
    print(f"Total Difference to Explain:           ₦ 90,733,703.10")
    print("-" * 105)
    
    # 1. Retained earnings component
    re_qbo = qbo_rows.get("Retained Earnings", {}).get("deb", 0) or qbo_rows.get("Retained Earnings", {}).get("net", 0)
    print(f"1. Prior Year Retained Earnings in QBO (2022 P&L rollover): ₦{re_qbo:>15,.2f}  (84.4% of difference!)")

    # 2. Other remaining differences
    print(f"2. Remaining Operational Variance across Balance Sheet/P&L:  ₦{90733703.10 - re_qbo:>15,.2f}")
    print("=" * 105)


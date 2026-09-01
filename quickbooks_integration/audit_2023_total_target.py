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
    qbo_rows = []
    rows = qbo_tb.get("Rows", {}).get("Row", [])
    
    def parse_rows(row_list):
        for row in row_list:
            if "ColData" in row:
                cols = row["ColData"]
                acc_name = cols[0].get("value")
                deb = flt(cols[1].get("value", 0))
                crd = flt(cols[2].get("value", 0))
                if acc_name and (deb or crd):
                    qbo_rows.append({"account": acc_name, "deb": deb, "crd": crd, "net": deb - crd})
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
    print(f"QuickBooks 2023 Total Target:        ₦410,118,984.99")
    print(f"ERPNext 2023 UI Closing Total (Net): ₦{leaf_dr:,.2f}")
    print(f"Difference:                         ₦{410118984.99 - leaf_dr:,.2f}")
    print("=" * 80)


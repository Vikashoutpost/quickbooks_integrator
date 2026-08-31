import frappe
import requests
import json
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def compare_tb():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date=2022-01-01&end_date=2022-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    if r.status_code == 401:
        token = refresh_qb_token(settings)
        headers["Authorization"] = f"Bearer {token}"
        r = requests.get(endpoint, headers=headers)

    qbo_tb = r.json()
    
    # Parse QBO rows
    qbo_accounts = {}
    rows = qbo_tb.get("Rows", {}).get("Row", [])
    
    def parse_rows(row_list):
        for row in row_list:
            if "ColData" in row:
                cols = row["ColData"]
                acc_name = cols[0].get("value")
                deb = flt(cols[1].get("value", 0))
                crd = flt(cols[2].get("value", 0))
                if acc_name and (deb or crd):
                    qbo_accounts[acc_name] = {"deb": deb, "crd": crd}
            if "Rows" in row:
                parse_rows(row["Rows"].get("Row", []))

    parse_rows(rows)

    # Get ERPNext GL for 2022
    erp_gl = frappe.db.sql("""
        SELECT account, SUM(debit) as deb, SUM(credit) as crd, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        GROUP BY account
        ORDER BY account
    """, as_dict=True)

    print("=" * 110)
    print(f"{'ACCOUNT NAME':<45} | {'QBO DEBIT':>14} | {'QBO CREDIT':>14} | {'ERP DEBIT':>14} | {'ERP CREDIT':>14}")
    print("=" * 110)

    for q_acc, vals in sorted(qbo_accounts.items()):
        print(f"{q_acc:<45} | {vals['deb']:>14,.2f} | {vals['crd']:>14,.2f} | {'-':>14} | {'-':>14}")

    print("=" * 110)
    print(f"Total QBO Accounts in 2022: {len(qbo_accounts)}")
    print(f"Total ERP Accounts in 2022: {len(erp_gl)}")
    print("=" * 110)


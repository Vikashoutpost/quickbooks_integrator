import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def audit_2022():
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
                    qbo_accounts[acc_name] = {"deb": deb, "crd": crd, "net": deb - crd}
            if "Rows" in row:
                parse_rows(row["Rows"].get("Row", []))

    parse_rows(rows)

    erp_gl = frappe.db.sql("""
        SELECT account, SUM(debit) as deb, SUM(credit) as crd, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        GROUP BY account
        ORDER BY account
    """, as_dict=True)

    erp_dict = {g["account"]: g for g in erp_gl}

    print("=== ERPNEXT 2022 GL ACCOUNTS ===")
    for a, g in sorted(erp_dict.items()):
        print(f"{a:<50} | Dr: {g['deb']:>14,.2f} | Cr: {g['crd']:>14,.2f} | Net: {g['net']:>14,.2f}")


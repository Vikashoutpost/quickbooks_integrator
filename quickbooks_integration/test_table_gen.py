import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def generate_table(fiscal_year, start_date, end_date):
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date={start_date}&end_date={end_date}"
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

    erp_rows = frappe.db.sql("""
        SELECT account, SUM(debit) as deb, SUM(credit) as crd, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN %s AND %s
          AND is_cancelled = 0
        GROUP BY account
    """, (start_date, end_date), as_dict=True)
    erp_dict = {r["account"]: r for r in erp_rows}

    print(f"Loaded {len(qbo_rows)} QBO rows and {len(erp_dict)} ERP rows for {fiscal_year}")


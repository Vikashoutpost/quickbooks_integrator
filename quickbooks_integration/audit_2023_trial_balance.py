import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
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

    # ERPNext 2023 activity (and closing for balance sheet)
    # Let's inspect all accounts in ERPNext
    erp_gl = frappe.db.sql("""
        SELECT account, 
               SUM(debit) - SUM(credit) as net_activity,
               SUM(debit) as deb,
               SUM(credit) as crd
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND is_cancelled = 0
        GROUP BY account
        ORDER BY account
    """, as_dict=True)

    print("=" * 115)
    print("                      2023 QUICKBOOKS TRIAL BALANCE ACCOUNTS")
    print("=" * 115)
    print(f"{'QBO ACCOUNT NAME':<45} | {'QBO DEBIT':>14} | {'QBO CREDIT':>14} | {'QBO NET':>14}")
    print("-" * 115)
    total_dr = 0
    total_cr = 0
    for q in qbo_rows:
        total_dr += q["deb"]
        total_cr += q["crd"]
        print(f"{q['account']:<45} | {q['deb']:>14,.2f} | {q['crd']:>14,.2f} | {q['net']:>14,.2f}")
    print("=" * 115)
    print(f"{'TOTAL':<45} | {total_dr:>14,.2f} | {total_cr:>14,.2f} |")
    print("=" * 115)


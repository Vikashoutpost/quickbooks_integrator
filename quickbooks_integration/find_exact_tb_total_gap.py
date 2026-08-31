import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date=2022-01-01&end_date=2022-12-31"
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

    # ERPNext Trial Balance Closing Balances
    erp_gl = frappe.db.sql("""
        SELECT account, 
               SUM(debit) - SUM(credit) as net_balance,
               SUM(debit) as deb,
               SUM(credit) as crd
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        GROUP BY account
        HAVING net_balance != 0
        ORDER BY account
    """, as_dict=True)

    print("=== QBO ROWS IN TRIAL BALANCE ===")
    total_qbo_dr = sum(r["deb"] for r in qbo_rows)
    total_qbo_cr = sum(r["crd"] for r in qbo_rows)
    print(f"Total QBO Dr: {total_qbo_dr:,.2f} | Total QBO Cr: {total_qbo_cr:,.2f}")

    print("\n=== ERPNEXT ROWS IN TRIAL BALANCE ===")
    total_erp_dr = sum(g["net_balance"] for g in erp_gl if g["net_balance"] > 0)
    total_erp_cr = sum(-g["net_balance"] for g in erp_gl if g["net_balance"] < 0)
    print(f"Total ERP Closing Dr: {total_erp_dr:,.2f} | Total ERP Closing Cr: {total_erp_cr:,.2f}")

    diff = total_qbo_dr - total_erp_dr
    print(f"\nGAP TO RECONCILE: {diff:,.2f}")

    # Print all QBO rows vs ERPNext rows
    print("\n" + "=" * 100)
    print(f"{'QBO ACCOUNT':<45} | {'QBO DR':>14} | {'QBO CR':>14}")
    print("=" * 100)
    for q in qbo_rows:
        print(f"{q['account']:<45} | {q['deb']:>14,.2f} | {q['crd']:>14,.2f}")

    print("\n" + "=" * 100)
    print(f"{'ERPNEXT ACCOUNT':<55} | {'CLOSING DR':>14} | {'CLOSING CR':>14}")
    print("=" * 100)
    for e in erp_gl:
        dr = e["net_balance"] if e["net_balance"] > 0 else 0
        cr = -e["net_balance"] if e["net_balance"] < 0 else 0
        print(f"{e['account']:<55} | {dr:>14,.2f} | {cr:>14,.2f}")


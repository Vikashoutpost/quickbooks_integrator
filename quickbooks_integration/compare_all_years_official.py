import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def audit_year(start_date, end_date, year_str):
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    if r.status_code == 401:
        token = refresh_qb_token(settings)
        headers["Authorization"] = f"Bearer {token}"
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

    # Official ERPNext Trial Balance Engine
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": year_str,
        "from_date": start_date,
        "to_date": end_date,
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)

    erp_total_row = [d for d in data if d.get("account_name") == "'Total'"]
    closing_dr = erp_total_row[0].get("closing_debit", 0) if erp_total_row else 0
    closing_cr = erp_total_row[0].get("closing_credit", 0) if erp_total_row else 0

    qbo_total_dr = sum(r["deb"] for r in qbo_rows)
    qbo_total_cr = sum(r["crd"] for r in qbo_rows)

    accum_dep_qbo = sum(r["crd"] for r in qbo_rows if "accumulated depreciation" in r["account"].lower())
    erp_adjusted_gross = closing_dr + accum_dep_qbo

    print(f"\n{'=' * 90}")
    print(f"               OFFICIAL TRIAL BALANCE AUDIT — YEAR {year_str}")
    print(f"{'=' * 90}")
    print(f"QuickBooks Gross Trial Balance Total:          ₦{qbo_total_dr:>18,.2f}")
    print(f"Accumulated Depreciation (Contra-Asset):       ₦{accum_dep_qbo:>18,.2f}")
    print(f"ERPNext Net Closing Balance Total:             ₦{closing_dr:>18,.2f}")
    print(f"ERPNext Gross Adjusted Total (+ Accum. Dep.):  ₦{erp_adjusted_gross:>18,.2f}")
    print(f"Variance ($\Delta$):                           ₦{qbo_total_dr - erp_adjusted_gross:>18,.2f}")
    print(f"{'=' * 90}")

def run_all():
    audit_year("2022-01-01", "2022-12-31", "2022")
    audit_year("2023-01-01", "2023-12-31", "2023")
    audit_year("2024-01-01", "2024-12-31", "2024")
    audit_year("2025-01-01", "2025-06-30", "2025")


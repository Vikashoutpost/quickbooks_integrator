import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def compare_year(start_date, end_date, year_label):
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

    # ERPNext Trial Balance for same period
    erp_gl = frappe.db.sql("""
        SELECT account, 
               SUM(debit) - SUM(credit) as net_balance,
               SUM(debit) as deb,
               SUM(credit) as crd
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN %s AND %s
          AND is_cancelled = 0
        GROUP BY account
        HAVING net_balance != 0
        ORDER BY account
    """, (start_date, end_date), as_dict=True)

    qbo_total_dr = sum(r["deb"] for r in qbo_rows)
    qbo_total_cr = sum(r["crd"] for r in qbo_rows)
    erp_closing_dr = sum(g["net_balance"] for g in erp_gl if g["net_balance"] > 0)
    erp_closing_cr = sum(-g["net_balance"] for g in erp_gl if g["net_balance"] < 0)
    
    # Check Accumulated Depreciation in QBO
    accum_dep_qbo = sum(r["crd"] for r in qbo_rows if "accumulated depreciation" in r["account"].lower())
    erp_net_with_contra = erp_closing_dr + accum_dep_qbo

    diff = qbo_total_dr - erp_closing_dr

    print(f"\n{'=' * 85}")
    print(f"            YEAR {year_label} TRIAL BALANCE ({start_date} to {end_date})")
    print(f"{'=' * 85}")
    print(f"QBO Total Debit/Credit:       ₦{qbo_total_dr:>18,.2f}")
    print(f"ERPNext Closing Debit/Credit: ₦{erp_closing_dr:>18,.2f}")
    print(f"Accum. Depreciation (Contra): ₦{accum_dep_qbo:>18,.2f}")
    print(f"ERPNext Adjusted Gross Total: ₦{erp_net_with_contra:>18,.2f}")
    print(f"Variance (Gross Difference):  ₦{qbo_total_dr - erp_net_with_contra:>18,.2f}")
    print(f"{'-' * 85}")
    print(f"QBO Accounts Count:           {len(qbo_rows):>18}")
    print(f"ERPNext Accounts Count:       {len(erp_gl):>18}")
    print(f"{'=' * 85}")

def run_all_years():
    periods = [
        ("2022-01-01", "2022-12-31", "2022"),
        ("2023-01-01", "2023-12-31", "2023"),
        ("2024-01-01", "2024-12-31", "2024"),
        ("2025-01-01", "2025-06-30", "2025 (H1 - QBO Cutoff)"),
        ("2022-01-01", "2025-06-30", "ALL TIME (2022 to mid-2025)"),
    ]
    for s, e, y in periods:
        compare_year(s, e, y)


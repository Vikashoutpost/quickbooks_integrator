import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def audit_year(fiscal_year, start_date, end_date):
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

    # QBO Total
    qbo_total_dr = sum(r["deb"] for r in qbo_rows.values())
    qbo_total_cr = sum(r["crd"] for r in qbo_rows.values())

    # ERPNext Trial Balance
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": fiscal_year,
        "from_date": start_date,
        "to_date": end_date,
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0,
        "show_group_accounts": 1
    })
    columns, data = run_erpnext_tb(filters)
    
    erp_opening_dr = 0.0
    erp_opening_cr = 0.0
    erp_debit = 0.0
    erp_credit = 0.0
    erp_closing_dr = 0.0
    erp_closing_cr = 0.0

    for row in data:
        if row.get("account_name") == "'Total'":
            erp_opening_dr = flt(row.get("opening_debit", 0))
            erp_opening_cr = flt(row.get("opening_credit", 0))
            erp_debit = flt(row.get("debit", 0))
            erp_credit = flt(row.get("credit", 0))
            erp_closing_dr = flt(row.get("closing_debit", 0))
            erp_closing_cr = flt(row.get("closing_credit", 0))

    print("=" * 95)
    print(f"                      AUDIT SUMMARY FOR FY {fiscal_year} ({start_date} to {end_date})")
    print("=" * 95)
    print(f"QuickBooks Grand Total:            ₦{qbo_total_dr:>18,.2f}")
    print(f"ERPNext Opening Total (Dr/Cr):     ₦{erp_opening_dr:>18,.2f}")
    print(f"ERPNext Period Activity Debit:     ₦{erp_debit:>18,.2f}")
    print(f"ERPNext Period Activity Credit:    ₦{erp_credit:>18,.2f}")
    print(f"ERPNext UI Closing Total (Dr):     ₦{erp_closing_dr:>18,.2f}")
    print(f"ERPNext UI Closing Total (Cr):     ₦{erp_closing_cr:>18,.2f}")
    print("=" * 95)

def run():
    print("\n" + "#" * 95)
    print("           COMPREHENSIVE MULTI-YEAR AUDIT (2022, 2023, 2024, 2025)")
    print("#" * 95)
    audit_year("2022", "2022-01-01", "2022-12-31")
    audit_year("2023", "2023-01-01", "2023-12-31")
    audit_year("2024", "2024-01-01", "2024-12-31")
    audit_year("2025", "2025-01-01", "2025-12-31")


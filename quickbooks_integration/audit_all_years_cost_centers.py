import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def audit_year_with_cost_centers(start_date, end_date, year_str):
    # 1. Fetch QBO Trial Balance for Year
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date={start_date}&end_date={end_date}"
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
    qbo_total_dr = sum(r["deb"] for r in qbo_rows)
    accum_dep = sum(r["crd"] for r in qbo_rows if "accumulated depreciation" in r["account"].lower())

    # 2. ERPNext Trial Balance leaf accounts sum (UI Closing Column calculation)
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": year_str,
        "from_date": start_date,
        "to_date": end_date,
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)

    # Compute Net UI Closing Dr and Cr for leaf rows (is_group = 0)
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

    # 3. Cost Center breakdown for the Year in ERPNext
    cc_data = frappe.db.sql("""
        SELECT cost_center, 
               COUNT(*) as txns, 
               SUM(debit) as deb, 
               SUM(credit) as crd
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN %s AND %s
          AND is_cancelled = 0
        GROUP BY cost_center
        ORDER BY deb DESC
    """, (start_date, end_date), as_dict=True)

    print("\n" + "=" * 105)
    print(f"                       YEAR {year_str} TRIAL BALANCE & COST CENTER SUMMARY")
    print("=" * 105)
    print(f"QuickBooks Gross Trial Balance Total:          ₦{qbo_total_dr:>18,.2f}")
    print(f"Accumulated Depreciation (Contra-Asset):       ₦{accum_dep:>18,.2f}")
    print(f"ERPNext UI Closing Column Total (Net):         ₦{leaf_dr:>18,.2f}")
    print(f"ERPNext Adjusted Gross (+ Accum. Dep.):        ₦{leaf_dr + accum_dep:>18,.2f}")
    print(f"Variance ($\Delta$):                           ₦{qbo_total_dr - (leaf_dr + accum_dep):>18,.2f}")
    print("-" * 105)
    print("COST CENTER DISTRIBUTION (TURNOVER):")
    for cc in cc_data:
        cname = cc.cost_center or "[No Cost Center]"
        print(f"  • {cname:<35} | Txns: {cc.txns:>5} | Debit: ₦{cc.deb:>16,.2f} | Credit: ₦{cc.crd:>16,.2f}")
    print("=" * 105)

def run():
    years = [
        ("2022-01-01", "2022-12-31", "2022"),
        ("2023-01-01", "2023-12-31", "2023"),
        ("2024-01-01", "2024-12-31", "2024"),
        ("2025-01-01", "2025-06-30", "2025"),
    ]
    for s, e, y in years:
        audit_year_with_cost_centers(s, e, y)


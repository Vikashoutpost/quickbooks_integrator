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

    # 2. Fetch ERPNext 2023 Trial Balance (official engine)
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 1,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)
    erp_leaf_rows = {}
    for row in data:
        if row.get("account") and not row.get("is_group") and row.get("account_name") != "'Total'":
            c_dr = flt(row.get("closing_debit", 0))
            c_cr = flt(row.get("closing_credit", 0))
            net = c_dr - c_cr
            erp_leaf_rows[row.get("account")] = {"deb": c_dr, "crd": c_cr, "net": net}

    print("=" * 110)
    print("                      2023 QUICKBOOKS ROWS VS ERPNEXT")
    print("=" * 110)
    print(f"{'QBO ACCOUNT':<42} | {'QBO DR':>13} | {'QBO CR':>13} | {'QBO NET':>13}")
    print("-" * 110)
    qbo_total_dr = sum(q["deb"] for q in qbo_rows)
    qbo_total_cr = sum(q["crd"] for q in qbo_rows)
    for q in qbo_rows:
        print(f"{q['account']:<42} | {q['deb']:>13,.2f} | {q['crd']:>13,.2f} | {q['net']:>13,.2f}")
    print("=" * 110)
    print(f"Total QBO Dr: ₦{qbo_total_dr:,.2f} | Total QBO Cr: ₦{qbo_total_cr:,.2f}")

    print("\n" + "=" * 110)
    print("                      2023 ERPNEXT LEAF ACCOUNTS")
    print("=" * 110)
    print(f"{'ERPNEXT ACCOUNT':<50} | {'CLOSING DR':>14} | {'CLOSING CR':>14}")
    print("-" * 110)
    erp_tot_dr = sum(e["net"] for e in erp_leaf_rows.values() if e["net"] > 0)
    erp_tot_cr = sum(-e["net"] for e in erp_leaf_rows.values() if e["net"] < 0)
    for acc, val in sorted(erp_leaf_rows.items()):
        if val["net"] != 0:
            dr = val["net"] if val["net"] > 0 else 0
            cr = -val["net"] if val["net"] < 0 else 0
            print(f"{acc:<50} | {dr:>14,.2f} | {cr:>14,.2f}")
    print("=" * 110)
    print(f"Total ERP Closing Dr: ₦{erp_tot_dr:,.2f} | Total ERP Closing Cr: ₦{erp_tot_cr:,.2f}")
    print(f"QBO Gross vs ERP Closing Dr Gap: ₦{qbo_total_dr - erp_tot_dr:,.2f}")


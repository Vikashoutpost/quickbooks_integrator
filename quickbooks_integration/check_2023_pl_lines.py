import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    # 1. Fetch 2023 QBO Trial Balance
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date=2023-01-01&end_date=2023-12-31"
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

    # 2. Fetch 2023 ERPNext Activity (Turnover) for P&L
    erp_pl = frappe.db.sql("""
        SELECT account, 
               SUM(debit) as deb,
               SUM(credit) as crd,
               SUM(debit) - SUM(credit) as net_activity
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND is_cancelled = 0
        GROUP BY account
    """, as_dict=True)
    erp_dict = {g["account"]: g["net_activity"] for g in erp_pl}

    MAPPING_2023_EXPENSES = {
        "Audit Expenses": ["403080 - Audit Expenses - MTL"],
        "Bank charges": ["403100 - Bank Charges - MTL"],
        "Business Promotion and Marketing": ["403120 - Business Promotion And Marketing - MTL"],
        "Dues and subscriptions": ["403160 - Dues And Subscriptions - MTL"],
        "Electricity Expenses": ["403170 - Electricity Expenses - MTL"],
        "Insurance - General": ["403230 - Insurance - General - MTL"],
        "Insurance- Medical": ["403250 - Insurance - Medical - MTL"],
        "Interest expense": ["403260 - Interest Expense - MTL"],
        "Internet and Domain Expenses": ["403270 - Internet And Domain Expenses - MTL"],
        "Legal and professional fees": ["403280 - Legal And Professional Fees - MTL"],
        "Meals and entertainment": ["403310 - Meals And Entertainment - MTL"],
        "Office expenses": ["403320 - Office Expenses - MTL"],
        "Post and Telecommunication": ["403370 - Post And Telecommunication - MTL"],
        "Rent or lease payments": ["403390 - Rent Or Lease Payments - MTL"],
        "Repairs and Maintenance": ["403400 - Repairs And Maintenance - Other Assets - MTL"],
        "Salaries and Wages": ["403430 - Salaries And Wages - MTL"],
        "Staff Training and Welfare": ["403460 - Staff Training And Welfare - MTL"],
        "Stationery and printing": ["403470 - Stationery And Printing - MTL"],
        "Statutory Fines": ["403480 - Statutory Fines - MTL"],
        "Transportation": ["403490 - Transportation - MTL"],
        "Travel expenses - general and admin expenses": ["403510 - Travel Expenses - MTL"],
        "Gain on disposal of assets": ["403610 - Gain on Disposal of Assets - MTL"],
        "Interest income": ["403620 - Interest Income - MTL"],
        "Depreciation": ["403680 - Depreciation - MTL"],
        "Foreign Exchange Fluctuation": ["403690 - Foreign Exchange Fluctuation - MTL"],
    }

    print("=" * 125)
    print("                      2023 P&L LINE-BY-LINE AUDIT")
    print("=" * 125)
    print(f"{'QBO ACCOUNT NAME':<45} | {'QBO DEBIT/CREDIT':>16} | {'ERP ACTIVITY':>16} | {'VARIANCE':>12} | STATUS")
    print("-" * 125)

    for q_acc, e_list in MAPPING_2023_EXPENSES.items():
        q_val = qbo_rows.get(q_acc, {}).get("net", 0.0)
        e_val = sum(erp_dict.get(e, 0.0) for e in e_list)
        diff = q_val - e_val
        status = "✅ MATCH" if abs(diff) < 500.0 else f"⚠️ DIFF: {diff:,.2f}"
        print(f"{q_acc:<45} | {q_val:>16,.2f} | {e_val:>16,.2f} | {diff:>12,.2f} | {status}")

    print("=" * 125)


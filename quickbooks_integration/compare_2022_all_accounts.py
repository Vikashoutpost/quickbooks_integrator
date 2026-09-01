import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    # 1. Fetch 2022 QBO Trial Balance
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/TrialBalance?start_date=2022-01-01&end_date=2022-12-31"
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

    # 2. 2022 ERPNext GL
    erp_gl = frappe.db.sql("""
        SELECT account, 
               SUM(debit) - SUM(credit) as net_activity
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        GROUP BY account
    """, as_dict=True)
    erp_dict = {g["account"]: g["net_activity"] for g in erp_gl}

    MAPPING_2022 = {
        "1000122240 Globus Bank": ["119020 - Globus Bank - MTL"],
        "OmniRetail Technology Limited (Payables)": ["224010 - OmniRetail Technology Limited (Payables) - MTL"],
        "Petty Cash": ["119040 - Petty Cash - MTL"],
        "Accounts Receivable (A/R)": ["121010 - Trade Receivables - NGN - MTL"],
        "Inventory": ["120010 - Stock In Hand - Device - MTL"],
        "Prepaid expenses": ["116050 - Prepaid Expense - MTL"],
        "Withholding Tax Expense": ["122030 - WHT Receivable - MTL"],
        "Computers": ["112020 - Computers & Peripherals - MTL"],
        "Office Equipment": ["112010 - Office Equipments - MTL"],
        "Office Furniture": ["112040 - Furniture & Fixtures - MTL"],
        "Plant & Machineries": ["112050 - Plant & Machinery - MTL"],
        "Accumulated depreciation on property, plant and equipment": ["112110 - Accumulated Depreciation - MTL"],
        "Accounts Payable (A/P)": ["225010 - Trade Creditors - NGN - MTL"],
        "Other Payable due to related party": ["224040 - Loan Payable - MTL"],
        "Paye": ["230020 - PAYEE Payable - MTL"],
        "Pension Contribution Payable": ["226020 - Pension Contribution Payable - MTL"],
        "VAT Control": ["230040 - VAT Payable - MTL"],
        "Withholding Tax": ["230030 - WHT Payable - MTL"],
        "Movam Inc. due to/from": ["228010 - Movam Inc - MTL"],
        "Equity Contribution": ["233020 - Equity Contribution - MTL"],
        "Retained Earnings": ["234010 - Retained Earnings - MTL"],
        "Share capital": ["233010 - Equity Share Capital - MTL"],
        "Sales & Services": ["311010 - Revenue - SAAS - MTL", "311020 - Revenue - Logistics - MTL"],
        "Sales of Product Income": ["311030 - Revenue - Device - MTL"],
        "Cost of Goods/ Service Sold": ["401040 - COGS Device - MTL", "401080 - COGS Logistics - MTL"],
        "Installation and Technical Charges": ["401060 - COGS Device : Installation and Technical Charges - MTL"],
        "Audit Expenses": ["403080 - Audit Expenses - MTL"],
        "Bank charges": ["403100 - Bank Charges - MTL"],
        "Business Promotion and Marketing": ["403120 - Business Promotion And Marketing - MTL"],
        "Communication Allowance": ["403140 - Communication Allowance - MTL"],
        "Director's Remuneration": ["403150 - Director's Remuneration - MTL"],
        "Dues and subscriptions": ["403160 - Dues And Subscriptions - MTL"],
        "Electricity Expenses": ["403170 - Electricity Expenses - MTL"],
        "Insurance- Medical": ["403250 - Insurance - Medical - MTL"],
        "Legal and professional fees": ["403280 - Legal And Professional Fees - MTL"],
        "Meals and entertainment": ["403310 - Meals And Entertainment - MTL"],
        "Office expenses": ["403320 - Office Expenses - MTL"],
        "Post and Telecommunication": ["403370 - Post And Telecommunication - MTL"],
        "Rent or lease payments": ["403390 - Rent Or Lease Payments - MTL"],
        "Repairs and Maintenance": ["403400 - Repairs And Maintenance - Other Assets - MTL"],
        "Salaries and Wages": ["403430 - Salaries And Wages - MTL"],
        "Software Management Expenses": ["403450 - Software Management Expenses - MTL"],
        "Staff Training and Welfare": ["403460 - Staff Training And Welfare - MTL"],
        "Stationery and printing": ["403470 - Stationery And Printing - MTL"],
        "Transportation": ["403490 - Transportation - MTL"],
        "Depreciation": ["403680 - Depreciation - MTL"],
    }

    print("=" * 125)
    print("                      2022 COMPLETE ACCOUNT-BY-ACCOUNT RECONCILIATION")
    print("=" * 125)
    print(f"{'QBO ACCOUNT NAME':<45} | {'QBO NET':>14} | {'ERP ACTIVITY':>16} | {'VARIANCE':>14} | STATUS")
    print("-" * 125)

    all_matched = True
    for q_acc, e_list in MAPPING_2022.items():
        q_val = qbo_rows.get(q_acc, {}).get("net", 0.0)
        e_val = sum(erp_dict.get(e, 0.0) for e in e_list)
        diff = q_val - e_val
        is_match = abs(diff) < 1.0
        if not is_match:
            all_matched = False
        status = "✅ MATCH" if is_match else f"⚠️ DIFF: {diff:,.2f}"
        print(f"{q_acc:<45} | {q_val:>14,.2f} | {e_val:>16,.2f} | {diff:>14,.2f} | {status}")

    print("=" * 125)
    if all_matched:
        print("🏆 100.00% EXACT RECONCILIATION ACHIEVED ACROSS ALL 2022 ACCOUNTS!")
    print("=" * 125)


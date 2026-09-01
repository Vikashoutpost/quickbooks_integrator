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

    # 2. Fetch ERPNext 2023 Trial Balance without unclosed FY P&L
    filters = frappe._dict({
        "company": "Movam Technologies Limited",
        "fiscal_year": "2023",
        "from_date": "2023-01-01",
        "to_date": "2023-12-31",
        "show_unclosed_fy_pl_balances": 0,
        "with_period": 0
    })
    columns, data = run_erpnext_tb(filters)
    erp_leaf_rows = {}
    for row in data:
        if row.get("account") and not row.get("is_group") and row.get("account_name") != "'Total'":
            c_dr = flt(row.get("closing_debit", 0))
            c_cr = flt(row.get("closing_credit", 0))
            net = c_dr - c_cr
            erp_leaf_rows[row.get("account")] = net

    MAPPING_2023 = {
        "1000122240 Globus Bank": ["119020 - Globus Bank - MTL"],
        "2002260771 FCMB Bank": ["119010 - FCMB Bank - MTL"],
        "Petty Cash": ["119040 - Petty Cash - MTL"],
        "Accounts Receivable (A/R)": ["121010 - Trade Receivables - NGN - MTL", "121020 - Trade Receivables - USD - MTL", "QB-80 - Accounts Receivable (A/R) - MTL"],
        "Inventory": ["120010 - Stock In Hand - Device - MTL", "QB-58 - Inventory - MTL"],
        "Prepaid expenses": ["116050 - Prepaid Expense - MTL"],
        "Salary Advance": ["117020 - Staff Salary Advance - MTL"],
        "Withholding Tax Expense": ["122030 - WHT Receivable - MTL"],
        "Computers": ["112020 - Computers & Peripherals - MTL"],
        "Office Equipment": ["112010 - Office Equipments - MTL"],
        "Office Furniture": ["112040 - Furniture & Fixtures - MTL"],
        "Plant & Machineries": ["112050 - Plant & Machinery - MTL"],
        "Accumulated depreciation on property, plant and equipment": ["112110 - Accumulated Depreciation - MTL"],
        "Accounts Payable (A/P)": ["225010 - Trade Creditors - NGN - MTL", "225020 - Trade Creditors - USD - MTL", "QB-85 - Accounts Payable (A/P) - MTL"],
        "Deferred Revenue": ["226060 - Deferred Revenue - MTL"],
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
        "Cost of Goods/ Service Sold": ["401040 - COGS Device - MTL", "401080 - COGS Logistics - MTL", "QB-75 - Cost of Goods/ Service Sold - MTL"],
        "Freight and delivery - COS": ["401050 - COGS Device : Freight and delivery - MTL", "QB-62 - Freight and delivery - COS - MTL"],
        "Installation and Technical Charges": ["401060 - COGS Device : Installation and Technical Charges - MTL", "QB-102 - Installation and Technical Charges - MTL"],
        "Audit Expenses": ["403080 - Audit Expenses - MTL"],
        "Bank charges": ["403100 - Bank Charges - MTL"],
        "Business Promotion and Marketing": ["403120 - Business Promotion And Marketing - MTL"],
        "Dues and subscriptions": ["403160 - Dues And Subscriptions - MTL"],
        "Electricity Expenses": ["403170 - Electricity Expenses - MTL"],
        "Insurance - General": ["403230 - Insurance - General - MTL"],
        "Insurance- Medical": ["403250 - Insurance - Medical - MTL"],
        "Interest expense": ["403260 - Interest Expenses - MTL"],
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
        "Gain on disposal of assets": ["312020 - Gain/Loss on disposal of assets - MTL"],
        "Interest income": ["312010 - Interest Income - MTL"],
        "Depreciation": ["403680 - Depreciation - MTL"],
        "Foreign Exchange Fluctuation": ["403010 - Foreign Exchange Fluctuation - MTL"],
    }

    print("=" * 125)
    print("                      2023 BALANCE SHEET & P&L CLOSING AUDIT")
    print("=" * 125)
    print(f"{'QBO ACCOUNT NAME':<45} | {'QBO NET':>14} | {'ERP CLOSING':>16} | {'DIFF':>14} | STATUS")
    print("-" * 125)

    for q_acc, e_list in MAPPING_2023.items():
        q_val = qbo_rows.get(q_acc, {}).get("net", 0.0)
        e_val = sum(erp_leaf_rows.get(e, 0.0) for e in e_list)
        diff = q_val - e_val
        status = "✅ MATCH" if abs(diff) < 1.0 else f"⚠️ DIFF: {diff:,.2f}"
        print(f"{q_acc:<45} | {q_val:>14,.2f} | {e_val:>16,.2f} | {diff:>14,.2f} | {status}")


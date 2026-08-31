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
    qbo_accounts = {}
    rows = qbo_tb.get("Rows", {}).get("Row", [])
    
    def parse_rows(row_list):
        for row in row_list:
            if "ColData" in row:
                cols = row["ColData"]
                acc_name = cols[0].get("value")
                deb = flt(cols[1].get("value", 0))
                crd = flt(cols[2].get("value", 0))
                if acc_name and (deb or crd):
                    qbo_accounts[acc_name] = deb - crd
            if "Rows" in row:
                parse_rows(row["Rows"].get("Row", []))

    parse_rows(rows)

    erp_gl = frappe.db.sql("""
        SELECT account, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND is_cancelled = 0
        GROUP BY account
    """, as_dict=True)
    erp_accounts = {g["account"]: flt(g["net"]) for g in erp_gl}

    # Explicit Map from QBO Account Name -> ERPNext Account Name
    MAPPING = {
        "1000122240 Globus Bank": ["119020 - Globus Bank - MTL"],
        "Accounts Payable (A/P)": ["225010 - Trade Creditors - NGN - MTL"],
        "Accounts Receivable (A/R)": ["121010 - Trade Receivables - NGN - MTL", "QB-80 - Accounts Receivable (A/R) - MTL"],
        "Accumulated depreciation on property, plant and equipment": ["112110 - Accumulated Depreciation - MTL"],
        "Audit Expenses": ["403080 - Audit Expenses - MTL"],
        "Bank charges": ["403100 - Bank Charges - MTL"],
        "Business Promotion and Marketing": ["403120 - Business Promotion And Marketing - MTL"],
        "Communication Allowance": ["403140 - Communication Allowance - MTL"],
        "Computers": ["112020 - Computers & Peripherals - MTL"],
        "Cost of Goods/ Service Sold": ["401040 - COGS Device - MTL", "401080 - COGS Logistics - MTL", "QB-75 - Cost of Goods/ Service Sold - MTL"],
        "Depreciation": ["403680 - Depreciation - MTL"],
        "Director's Remuneration": ["403150 - Director's Remuneration - MTL"],
        "Dues and subscriptions": ["403160 - Dues And Subscriptions - MTL"],
        "Electricity Expenses": ["403170 - Electricity Expenses - MTL"],
        "Equity Contribution": ["233020 - Equity Contribution - MTL"],
        "Installation and Technical Charges": ["401060 - COGS Device : Installation and Technical Charges - MTL", "QB-102 - Installation and Technical Charges - MTL"],
        "Insurance- Medical": ["403250 - Insurance - Medical - MTL"],
        "Inventory": ["120010 - Stock In Hand - Device - MTL", "QB-58 - Inventory - MTL"],
        "Legal and professional fees": ["403280 - Legal And Professional Fees - MTL"],
        "Meals and entertainment": ["403310 - Meals And Entertainment - MTL"],
        "Office Equipment": ["112010 - Office Equipments - MTL"],
        "Office Furniture": ["112040 - Furniture & Fixtures - MTL"],
        "Office expenses": ["403320 - Office Expenses - MTL"],
        "Oluwaseyi Onasanya": ["224050 - Oluwaseyi Onasanya - MTL"],
        "Petty Cash": ["119040 - Petty Cash - MTL"],
        "Plant & Machineries": ["112050 - Plant & Machinery - MTL"],
        "Post and Telecommunication": ["403370 - Post And Telecommunication - MTL"],
        "Prepaid expenses": ["116050 - Prepaid Expense - MTL"],
        "Provision for Audit": ["229080 - Provision for Audit Fee - MTL"],
        "Rent or lease payments": ["403390 - Rent Or Lease Payments - MTL"],
        "Repairs and Maintenance": ["403400 - Repairs And Maintenance - Other Assets - MTL"],
        "Salaries and Wages": ["403430 - Salaries And Wages - MTL"],
        "Sales & Services": ["311010 - Revenue - SAAS - MTL", "311020 - Revenue - Logistics - MTL"],
        "Sales of Product Income": ["311030 - Revenue - Device - MTL"],
        "Share capital": ["233010 - Equity Share Capital - MTL"],
        "Software Management Expenses": ["403450 - Software Management Expenses - MTL"],
        "Staff Training and Welfare": ["403460 - Staff Training And Welfare - MTL"],
        "Stationery and printing": ["403470 - Stationery And Printing - MTL"],
        "Transportation": ["403490 - Transportation - MTL"],
        "VAT Control": ["230040 - VAT Payable - MTL"],
        "Withholding Tax": ["230030 - WHT Payable - MTL"],
        "Withholding Tax Expense": ["122030 - WHT Receivable - MTL"]
    }

    print("=" * 115)
    print(f"{'QBO ACCOUNT NAME':<40} | {'QBO NET':>14} | {'ERP NET':>14} | {'VARIANCE (DIFF)':>16} | STATUS")
    print("=" * 115)

    for q_acc, erp_list in sorted(MAPPING.items()):
        q_net = qbo_accounts.get(q_acc, 0.0)
        e_net = sum(erp_accounts.get(acc, 0.0) for acc in erp_list)
        diff = q_net - e_net
        status = "MATCH" if abs(diff) < 0.05 else "MISMATCH"
        print(f"{q_acc:<40} | {q_net:>14,.2f} | {e_net:>14,.2f} | {diff:>16,.2f} | {status}")


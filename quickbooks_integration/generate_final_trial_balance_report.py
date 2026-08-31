import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def generate_tb_report(start_date="2022-01-01", end_date="2022-12-31"):
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
    qbo_data = {}
    rows = qbo_tb.get("Rows", {}).get("Row", [])
    
    def parse_rows(row_list):
        for row in row_list:
            if "ColData" in row:
                cols = row["ColData"]
                acc_name = cols[0].get("value")
                deb = flt(cols[1].get("value", 0))
                crd = flt(cols[2].get("value", 0))
                if acc_name and (deb or crd):
                    qbo_data[acc_name] = {"deb": deb, "crd": crd, "net": deb - crd}
            if "Rows" in row:
                parse_rows(row["Rows"].get("Row", []))

    parse_rows(rows)

    # ERPNext GL Entries for the period
    erp_gl = frappe.db.sql("""
        SELECT account, SUM(debit) as deb, SUM(credit) as crd, SUM(debit) - SUM(credit) as net
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN %s AND %s
          AND is_cancelled = 0
        GROUP BY account
        ORDER BY account
    """, (start_date, end_date), as_dict=True)

    erp_dict = {g["account"]: {"deb": flt(g["deb"]), "crd": flt(g["crd"]), "net": flt(g["net"])} for g in erp_gl}

    # Consolidated Comparison Mapping
    print("\n" + "=" * 125)
    print(f"                      TRIAL BALANCE COMPARISON ({start_date} to {end_date})")
    print("=" * 125)
    print(f"{'ACCOUNT NAME / CATEGORY':<48} | {'QBO NET (NGN)':>16} | {'ERPNEXT NET (NGN)':>18} | {'VARIANCE':>14} | STATUS")
    print("-" * 125)

    MAPPING = {
        "1. Globus Bank": (["1000122240 Globus Bank"], ["119020 - Globus Bank - MTL"]),
        "2. Petty Cash": (["Petty Cash"], ["119040 - Petty Cash - MTL"]),
        "3. Accounts Receivable": (["Accounts Receivable (A/R)"], ["121010 - Trade Receivables - NGN - MTL", "QB-80 - Accounts Receivable (A/R) - MTL"]),
        "4. Inventory / Stock in Hand": (["Inventory"], ["120010 - Stock In Hand - Device - MTL", "QB-58 - Inventory - MTL"]),
        "5. Prepaid Expenses": (["Prepaid expenses"], ["116050 - Prepaid Expense - MTL"]),
        "6. Salary Advance": (["Salary Advance"], ["117020 - Staff Salary Advance - MTL"]),
        "7. WHT Receivable (Tax Expense)": (["Withholding Tax Expense"], ["122030 - WHT Receivable - MTL"]),
        "8. Computers & Peripherals": (["Computers"], ["112020 - Computers & Peripherals - MTL"]),
        "9. Office Equipment": (["Office Equipment"], ["112010 - Office Equipments - MTL"]),
        "10. Office Furniture": (["Office Furniture"], ["112040 - Furniture & Fixtures - MTL"]),
        "11. Plant & Machinery": (["Plant & Machineries"], ["112050 - Plant & Machinery - MTL"]),
        "12. Accumulated Depreciation": (["Accumulated depreciation on property, plant and equipment"], ["112110 - Accumulated Depreciation - MTL"]),
        "13. Accounts Payable": (["Accounts Payable (A/P)"], ["225010 - Trade Creditors - NGN - MTL", "QB-85 - Accounts Payable (A/P) - MTL"]),
        "14. Provision for Audit Fee": (["Provision for Audit"], ["229080 - Provision for Audit Fee - MTL"]),
        "15. Director Loan (Oluwaseyi)": (["Oluwaseyi Onasanya"], ["224050 - Oluwaseyi Onasanya - MTL"]),
        "16. VAT Control / Payable": (["VAT Control"], ["230040 - VAT Payable - MTL"]),
        "17. WHT Payable": (["Withholding Tax"], ["230030 - WHT Payable - MTL"]),
        "18. Equity Contribution": (["Equity Contribution"], ["233020 - Equity Contribution - MTL"]),
        "19. Share Capital": (["Share capital"], ["233010 - Equity Share Capital - MTL"]),
        "20. Revenue (SAAS + Device + Logistics)": (["Sales & Services", "Sales of Product Income"], ["311010 - Revenue - SAAS - MTL", "311020 - Revenue - Logistics - MTL", "311030 - Revenue - Device - MTL"]),
        "21. Cost of Goods Sold": (["Cost of Goods/ Service Sold"], ["401040 - COGS Device - MTL", "401080 - COGS Logistics - MTL", "QB-75 - Cost of Goods/ Service Sold - MTL"]),
        "22. Installation & Technical Charges": (["Installation and Technical Charges"], ["401060 - COGS Device : Installation and Technical Charges - MTL", "QB-102 - Installation and Technical Charges - MTL"]),
        "23. Audit Expenses": (["Audit Expenses"], ["403080 - Audit Expenses - MTL"]),
        "24. Bank Charges": (["Bank charges"], ["403100 - Bank Charges - MTL"]),
        "25. Business Promotion & Marketing": (["Business Promotion and Marketing"], ["403120 - Business Promotion And Marketing - MTL"]),
        "26. Communication Allowance": (["Communication Allowance"], ["403140 - Communication Allowance - MTL"]),
        "27. Director's Remuneration": (["Director's Remuneration"], ["403150 - Director's Remuneration - MTL"]),
        "28. Dues and Subscriptions": (["Dues and subscriptions"], ["403160 - Dues And Subscriptions - MTL"]),
        "29. Electricity Expenses": (["Electricity Expenses"], ["403170 - Electricity Expenses - MTL"]),
        "30. Insurance - Medical": (["Insurance- Medical"], ["403250 - Insurance - Medical - MTL"]),
        "31. Legal and Professional Fees": (["Legal and professional fees"], ["403280 - Legal And Professional Fees - MTL"]),
        "32. Meals and Entertainment": (["Meals and entertainment"], ["403310 - Meals And Entertainment - MTL"]),
        "33. Office Expenses": (["Office expenses"], ["403320 - Office Expenses - MTL"]),
        "34. Post and Telecommunication": (["Post and Telecommunication"], ["403370 - Post And Telecommunication - MTL"]),
        "35. Rent or Lease Payments": (["Rent or lease payments"], ["403390 - Rent Or Lease Payments - MTL"]),
        "36. Repairs and Maintenance": (["Repairs and Maintenance"], ["403400 - Repairs And Maintenance - Other Assets - MTL"]),
        "37. Salaries and Wages": (["Salaries and Wages"], ["403430 - Salaries And Wages - MTL"]),
        "38. Software Management Expenses": (["Software Management Expenses"], ["403450 - Software Management Expenses - MTL"]),
        "39. Staff Training and Welfare": (["Staff Training and Welfare"], ["403460 - Staff Training And Welfare - MTL"]),
        "40. Stationery and Printing": (["Stationery and printing"], ["403470 - Stationery And Printing - MTL"]),
        "41. Transportation": (["Transportation"], ["403490 - Transportation - MTL"]),
        "42. Depreciation Expense": (["Depreciation"], ["403680 - Depreciation - MTL"]),
    }

    match_count = 0
    total_items = len(MAPPING)

    for label, (q_list, e_list) in sorted(MAPPING.items(), key=lambda x: int(x[0].split('.')[0])):
        q_net = sum(qbo_data.get(q, {}).get("net", 0.0) for q in q_list)
        e_net = sum(erp_dict.get(e, {}).get("net", 0.0) for e in e_list)
        diff = q_net - e_net
        status = "✅ MATCH" if abs(diff) < 0.05 else f"⚠️ DIFF: {diff:,.2f}"
        if abs(diff) < 0.05:
            match_count += 1
        print(f"{label:<48} | {q_net:>16,.2f} | {e_net:>18,.2f} | {diff:>14,.2f} | {status}")

    print("=" * 125)
    
    # Grand Totals
    qbo_total_dr = sum(d["deb"] for d in qbo_data.values())
    qbo_total_cr = sum(d["crd"] for d in qbo_data.values())
    erp_total_dr = sum(d["deb"] for d in erp_dict.values())
    erp_total_cr = sum(d["crd"] for d in erp_dict.values())

    print(f"{'GRAND TOTAL (DEBIT)':<48} | {qbo_total_dr:>16,.2f} | {erp_total_dr:>18,.2f} | {qbo_total_dr - erp_total_dr:>14,.2f} |")
    print(f"{'GRAND TOTAL (CREDIT)':<48} | {qbo_total_cr:>16,.2f} | {erp_total_cr:>18,.2f} | {qbo_total_cr - erp_total_cr:>14,.2f} |")
    print("=" * 125)
    print(f"Summary: {match_count} / {total_items} Accounts 100% Matched.")
    print("=" * 125 + "\n")


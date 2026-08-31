import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    # 1. Fetch 2023 QBO General Ledger for target accounts
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger?start_date=2023-01-01&end_date=2023-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    data = r.json()

    target_names = [
        "Office expenses", "Travel expenses", "Repairs and Maintenance", 
        "Transportation", "Salaries and Wages", "Freight and delivery - COS"
    ]
    
    qbo_txns = []

    def parse_gl_section(section):
        header = section.get("Header", {})
        col_data = header.get("ColData", [])
        acc_name = col_data[0].get("value") if col_data else ""
        
        is_target = any(t.lower() in acc_name.lower() for t in target_names)
        
        rows = section.get("Rows", {}).get("Row", [])
        for row in rows:
            if "Header" in row:
                parse_gl_section(row)
            elif "ColData" in row and is_target:
                cols = row["ColData"]
                date = cols[0].get("value")
                txn_type = cols[1].get("value")
                num = cols[2].get("value")
                name = cols[3].get("value")
                memo = cols[4].get("value")
                amt = flt(cols[6].get("value", 0))
                qbo_txns.append({
                    "account": acc_name,
                    "date": date,
                    "type": txn_type,
                    "num": num,
                    "name": name,
                    "memo": memo,
                    "amt": amt
                })

    root_rows = data.get("Rows", {}).get("Row", [])
    for row in root_rows:
        if "Header" in row:
            parse_gl_section(row)

    print(f"Total target QBO transactions found: {len(qbo_txns)}")
    
    # Check 210,000 difference in Office Expenses
    print("\n--- QBO Office Expenses Transactions ---")
    for t in qbo_txns:
        if "office" in t["account"].lower():
            print(f"{t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")

    # Check 134,650.62 in Travel Expenses
    print("\n--- QBO Travel Expenses Transactions ---")
    for t in qbo_txns:
        if "travel" in t["account"].lower():
            print(f"{t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")

    # Check 31,464 in Repairs
    print("\n--- QBO Repairs Transactions ---")
    for t in qbo_txns:
        if "repair" in t["account"].lower():
            print(f"{t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")

    # Check 140,800 in Transportation
    print("\n--- QBO Transportation Transactions ---")
    for t in qbo_txns:
        if "transport" in t["account"].lower():
            print(f"{t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")

    # Check 47,925.25 in Freight
    print("\n--- QBO Freight Transactions ---")
    for t in qbo_txns:
        if "freight" in t["account"].lower():
            print(f"{t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")


import frappe
import requests
import json
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger?start_date=2023-01-01&end_date=2023-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    data = r.json()
    
    target_accounts = ["Insurance - General", "Interest expense", "Foreign Exchange Fluctuation", "Interest income", "Gain on disposal of assets"]
    found_txns = []

    def parse_gl_section(section):
        header = section.get("Header", {})
        col_data = header.get("ColData", [])
        acc_name = col_data[0].get("value") if col_data else ""
        
        # Check if acc_name matches
        is_target = any(t.lower() in acc_name.lower() for t in target_accounts)
        
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
                amt = cols[6].get("value")
                found_txns.append({
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

    print(f"Found {len(found_txns)} target transactions in 2023 QBO GL:")
    for t in found_txns:
        print(f"[{t['account']}] {t['date']} | {t['type']} #{t['num']} | {t['name']} | {t['amt']} | {t['memo']}")


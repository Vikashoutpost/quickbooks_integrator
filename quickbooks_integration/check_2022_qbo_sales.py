import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger?start_date=2022-01-01&end_date=2022-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    data = r.json()

    target_accounts = ["Sales & Services", "Sales of Product Income"]
    found_txns = []

    def parse_gl_section(section):
        header = section.get("Header", {})
        col_data = header.get("ColData", [])
        acc_name = col_data[0].get("value") if col_data else ""
        
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
                amt = flt(cols[6].get("value", 0))
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

    print(f"Found {len(found_txns)} Sales transactions in 2022 QBO GL:")
    for t in found_txns:
        print(f"[{t['account']}] {t['date']} | {t['type']} #{t['num']} | {t['name']} | ₦{t['amt']:,.2f} | {t['memo']}")


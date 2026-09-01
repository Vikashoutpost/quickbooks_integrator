import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    # 1. Fetch Bank Charges from QBO General Ledger
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger?start_date=2023-01-01&end_date=2023-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    data = r.json()

    qbo_bank_charges = []

    def parse_gl_section(section):
        header = section.get("Header", {})
        col_data = header.get("ColData", [])
        acc_name = col_data[0].get("value") if col_data else ""
        
        is_target = "bank charge" in acc_name.lower()
        
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
                qbo_bank_charges.append({
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

    print(f"Total Bank Charges in QBO: {len(qbo_bank_charges)} transactions (Sum = ₦{sum(t['amt'] for t in qbo_bank_charges):,.2f})")

    # 2. Fetch Bank Charges in ERPNext
    erp_bank_charges = frappe.db.sql("""
        SELECT posting_date, voucher_type, voucher_no, debit, credit, remarks
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
          AND account = '403100 - Bank Charges - MTL'
          AND is_cancelled = 0
    """, as_dict=True)
    print(f"Total Bank Charges in ERPNext: {len(erp_bank_charges)} transactions (Sum = ₦{sum(t['debit'] for t in erp_bank_charges):,.2f})")

    # Let's inspect differences
    qbo_amounts = [t["amt"] for t in qbo_bank_charges]
    erp_amounts = [t["debit"] for t in erp_bank_charges]
    
    missing_in_erp = []
    for t in qbo_bank_charges:
        if t["amt"] not in erp_amounts:
            missing_in_erp.append(t)

    print("\n--- Transactions in QBO Bank Charges not matching ERPNext: ---")
    for m in missing_in_erp:
        print(f"{m['date']} | {m['type']} #{m['num']} | ₦{m['amt']:,.2f} | {m['memo']}")


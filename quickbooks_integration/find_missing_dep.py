import frappe
import requests
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}

    q = "SELECT * FROM Deposit MAXRESULTS 500"
    r = requests.post(endpoint, headers=headers, data=q)
    deps = r.json().get("QueryResponse", {}).get("Deposit", [])
    print(f"Total Deposits in QBO: {len(deps)}")

    for d in deps:
        qb_id = d.get("Id")
        custom_id = f"DEP-{qb_id}"
        je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
        if not je:
            print(f"Missing Deposit: ID={qb_id}, TotalAmt={d.get('TotalAmt')}, Lines={len(d.get('Line', []))}")

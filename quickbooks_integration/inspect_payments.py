import frappe
import requests
import json
from quickbooks_integration.api.bill_sync import refresh_qb_token

def inspect_payments():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}

    for pid in ["78", "1854", "2244"]:
        q = f"SELECT * FROM Payment WHERE Id = '{pid}'"
        r = requests.post(endpoint, headers=headers, data=q)
        print(f"=== PAYMENT {pid} ===")
        print(json.dumps(r.json(), indent=2))


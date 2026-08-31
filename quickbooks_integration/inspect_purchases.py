import frappe
import requests
import json
from quickbooks_integration.api.bill_sync import refresh_qb_token

def inspect_purchases():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}

    q = "SELECT * FROM Purchase MAXRESULTS 3"
    r = requests.post(endpoint, headers=headers, data=q)
    if r.status_code == 401:
        token = refresh_qb_token(settings)
        headers["Authorization"] = f"Bearer {token}"
        r = requests.post(endpoint, headers=headers, data=q)

    purchases = r.json().get("QueryResponse", {}).get("Purchase", [])
    print(f"Total returned: {len(purchases)}")
    print(json.dumps(purchases, indent=2))


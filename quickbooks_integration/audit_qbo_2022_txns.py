import frappe
import requests
import json
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def audit_txns():
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger?start_date=2022-01-01&end_date=2022-12-31"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(endpoint, headers=headers)
    gl_data = r.json()

    print("Keys in GL Report:", gl_data.keys())
    # Save GL report for quick offline analysis
    with open("/home/dharanipathi/frappe-bench/apps/quickbooks_integration/quickbooks_integration/qbo_gl_2022.json", "w") as f:
        json.dump(gl_data, f, indent=2)
    print("Saved qbo_gl_2022.json")


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

    # Let's inspect Accounts in QBO to get their exact QBO IDs
    q_acc = f"{base_url}/v3/company/{realm_id}/query"
    headers_query = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}
    r = requests.post(q_acc, headers=headers_query, data="SELECT * FROM Account WHERE Name IN ('Prepaid expenses', 'Withholding Tax Expense', 'Inventory', 'Office expenses')")
    print(r.json())


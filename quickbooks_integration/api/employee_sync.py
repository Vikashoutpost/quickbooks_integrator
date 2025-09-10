import frappe
import requests
import json

@frappe.whitelist()
def sync_quickbooks_employees():
    try:
        # Load QuickBooks Settings
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        print("🔐 Access Token:", access_token)
        print("🏢 Realm ID:", realm_id)
        print("🌍 Environment:", environment)

        # Base URL depending on environment
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = "SELECT * FROM Employee"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        print("📡 Sending request to:", endpoint)
        print("🔎 Query:", query)

        response = requests.post(endpoint, headers=headers, data=query)

        print("📥 Response Code:", response.status_code)

        if response.status_code != 200:
            print("❌ Failed to fetch employees:", response.text)
            return "Failed to fetch employees. Check logs."

        employee_data = response.json()

        print("✅ Employee data fetched from QuickBooks:")
        print(json.dumps(employee_data, indent=2))  # Pretty print

        return "Employee data fetched successfully. Check server logs for details."

    except Exception as e:
        print("🔥 Error fetching employees:")
        frappe.log_error(frappe.get_traceback(), "QuickBooks Employee Sync Error")
        return f"Error occurred: {str(e)}"

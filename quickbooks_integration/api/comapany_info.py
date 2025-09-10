import requests
import frappe
import json
from frappe.utils.password import get_decrypted_password

@frappe.whitelist()
def get_quickbooks_company_info():
    try:
        # Fetch QuickBooks settings from your doctype
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        
        if not access_token or not realm_id:
            frappe.throw("QuickBooks Access Token or Realm ID is missing")
        
        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/companyinfo/{realm_id}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        company_info = response.json()
        print("Company Info:")
        print(json.dumps(company_info, indent=2))

        return company_info
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Company Info Fetch Error")
        return {"error": str(e)}

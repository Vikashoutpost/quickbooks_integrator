import frappe
import requests
import json
from frappe.utils.password import get_decrypted_password

def get_quickbooks_auth():
    """Get QuickBooks settings and access token"""
    settings = frappe.get_single("Quickbook Settings")
    access_token = settings.access_token
    realm_id = settings.realm_id
    environment = settings.environment or "sandbox"

    if environment == "sandbox":
        base_url = "https://sandbox-quickbooks.api.intuit.com"
    else:
        base_url = "https://quickbooks.api.intuit.com"

    return access_token, realm_id, base_url


@frappe.whitelist()
def sync_quickbooks_chart_of_accounts():
    try:
        access_token, realm_id, base_url = get_quickbooks_auth()

        url = f"{base_url}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        query = "select * from Account"
        response = requests.post(url, headers=headers, data=query)

        if response.status_code != 200:
            frappe.throw(f"QuickBooks API Error: {response.text}")

        data = response.json()
        print(json.dumps(data, indent=2))  

        if "QueryResponse" not in data or "Account" not in data["QueryResponse"]:
            frappe.throw("No accounts found in QuickBooks response")

        accounts = data["QueryResponse"]["Account"]

        company = frappe.defaults.get_user_default("Company")

        for acc in accounts:
            acc_name = acc.get("Name")
            acc_type = acc.get("AccountType")
            acc_subtype = acc.get("AccountSubType")
            acc_id = acc.get("Id")
            acc_number = acc.get("AcctNum") or f"QB-{acc_id}"  
            parent_id = acc.get("ParentRef", {}).get("value")

            existing = frappe.db.exists("Account", {"quickbooks_id": acc_id})
            if existing:
                continue

            account_type, root_type = map_quickbooks_type(acc_type, acc_subtype)

            parent_account = get_parent_account(parent_id)
            if not parent_id:  
                parent_account = get_default_root_account(root_type, company)

            if not parent_account:
                frappe.msgprint(f"Skipping {acc_name}, missing valid parent")
                continue

            is_group = 0 if parent_id else 1

            new_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": acc_name,
                "account_number": acc_number,
                "parent_account": parent_account,  
                "is_group": is_group,
                "account_type": account_type,
                "root_type": root_type if not parent_id else None,  
                "company": company,
                "quickbooks_id": acc_id
            })
            new_account.insert(ignore_permissions=True)

        return "✅ Chart of Accounts synced successfully from QuickBooks"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks COA Sync Error")
        return f"Error: {str(e)}"


def get_parent_account(parent_id):
    """Map QuickBooks parent account ID to ERPNext account"""
    if not parent_id:
        return None
    return frappe.db.get_value("Account", {"quickbooks_id": parent_id}, "name")


def get_default_root_account(root_type, company):
    """Map root_type to ERPNext's default root group accounts"""
    root_map = {
        "Asset": "All Assets",
        "Liability": "All Liabilities",
        "Equity": "All Equity",
        "Income": "All Income",
        "Expense": "All Expenses"
    }
    root_name = root_map.get(root_type)
    if not root_name:
        return None
    return frappe.db.get_value("Account", {"account_name": root_name, "company": company}, "name")


def map_quickbooks_type(acc_type, acc_subtype):
    """Map QuickBooks AccountType to ERPNext account_type and root_type"""
    mapping = {
        "Accounts Receivable": ("Receivable", "Asset"),
        "Accounts Payable": ("Payable", "Liability"),
        "Bank": ("Bank", "Asset"),
        "Credit Card": ("Credit Card", "Liability"),
        "Fixed Asset": ("Fixed Asset", "Asset"),
        "Other Asset": ("Current Asset", "Asset"),
        "Other Current Asset": ("Current Asset", "Asset"),
        "Other Current Liability": ("Current Liability", "Liability"),
        "Long Term Liability": ("Long Term Liability", "Liability"),
        "Equity": ("Equity", "Equity"),
        "Income": ("Income", "Income"),
        "Other Income": ("Income", "Income"),
        "Expense": ("Expense", "Expense"),
        "Other Expense": ("Expense", "Expense"),
        "Cost of Goods Sold": ("Cost of Goods Sold", "Expense")
    }
    return mapping.get(acc_type, (None, None))

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
        company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw("No default company found. Please set a Default Company in Global Defaults.")

        # Identify which accounts are parent accounts
        parent_ids = {acc.get("ParentRef", {}).get("value") for acc in accounts if acc.get("ParentRef", {}).get("value")}

        for acc in accounts:
            acc_name = acc.get("Name")
            acc_type = acc.get("AccountType")
            acc_subtype = acc.get("AccountSubType")
            acc_id = acc.get("Id")
            acc_number = acc.get("AcctNum") or f"QB-{acc_id}"  
            parent_id = acc.get("ParentRef", {}).get("value")

            is_parent = (acc_id in parent_ids) or acc.get("SubAccount") is False and (acc_id in parent_ids)

            # Check if account already exists
            existing_account = frappe.db.get_value("Account", {"account_name": acc_name, "company": company}, "name") or \
                               frappe.db.get_value("Account", {"account_number": acc_number, "company": company}, "name")
            if existing_account:
                # If this existing account needs to be a parent, ensure is_group is set to 1
                if is_parent:
                    is_grp = frappe.db.get_value("Account", existing_account, "is_group")
                    if not is_grp:
                        frappe.db.set_value("Account", existing_account, "is_group", 1)
                        frappe.db.commit()
                continue

            account_type, root_type = map_quickbooks_type(acc_type, acc_subtype)

            parent_account = get_parent_account(parent_id, company)
            if not parent_account:  
                parent_account = get_default_root_account(root_type, company)

            if not parent_account:
                frappe.msgprint(f"Skipping {acc_name}, missing valid parent")
                continue

            # Ensure parent_account is a group
            parent_is_grp = frappe.db.get_value("Account", parent_account, "is_group")
            if not parent_is_grp:
                frappe.db.set_value("Account", parent_account, "is_group", 1)
                frappe.db.commit()

            new_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": acc_name,
                "account_number": acc_number,
                "parent_account": parent_account,
                "is_group": 1 if is_parent else 0,
                "account_type": account_type if not is_parent else None,
                "company": company
            })
            new_account.insert(ignore_permissions=True)

        return "✅ Chart of Accounts synced successfully from QuickBooks"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks COA Sync Error")
        return f"Error: {str(e)}"


def get_parent_account(parent_id, company):
    """Map QuickBooks parent account ID to ERPNext account"""
    if not parent_id:
        return None
    return frappe.db.get_value("Account", {"account_number": f"QB-{parent_id}", "company": company}, "name")


def get_default_root_account(root_type, company):
    """Find top-level group account for the given root_type and company"""
    if not root_type or not company:
        return None

    # First try to find a top-level group account with no parent
    parent = frappe.db.get_value(
        "Account",
        {
            "root_type": root_type,
            "company": company,
            "is_group": 1,
            "parent_account": ["in", ["", None]]
        },
        "name"
    )

    # Fallback to any group account matching root_type
    if not parent:
        parent = frappe.db.get_value(
            "Account",
            {
                "root_type": root_type,
                "company": company,
                "is_group": 1
            },
            "name"
        )
    return parent


def map_quickbooks_type(acc_type, acc_subtype):
    """Map QuickBooks AccountType to ERPNext account_type and root_type"""
    mapping = {
        "Accounts Receivable": ("Receivable", "Asset"),
        "Accounts Payable": ("Payable", "Liability"),
        "Bank": ("Bank", "Asset"),
        "Credit Card": (None, "Liability"),
        "Fixed Asset": ("Fixed Asset", "Asset"),
        "Other Asset": (None, "Asset"),
        "Other Current Asset": (None, "Asset"),
        "Other Current Liability": (None, "Liability"),
        "Long Term Liability": (None, "Liability"),
        "Equity": ("Equity", "Equity"),
        "Income": ("Income Account", "Income"),
        "Other Income": ("Income Account", "Income"),
        "Expense": ("Expense Account", "Expense"),
        "Other Expense": ("Expense Account", "Expense"),
        "Cost of Goods Sold": ("Cost of Goods Sold", "Expense")
    }
    return mapping.get(acc_type, (None, None))

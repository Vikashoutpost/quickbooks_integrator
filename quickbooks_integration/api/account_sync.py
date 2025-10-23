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

        # Get default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw("No default company set in Global Defaults. Please configure it first.")

        print(f"Syncing {len(accounts)} accounts to company: {company}")

        # Identify which accounts have children (need to be groups)
        parent_ids_with_children = set()
        for acc in accounts:
            if acc.get("SubAccount", False) and acc.get("ParentRef"):
                parent_id = acc["ParentRef"].get("value")
                if parent_id:
                    parent_ids_with_children.add(parent_id)

        # First pass: Create parent accounts (non-subaccounts)
        parent_accounts = [acc for acc in accounts if not acc.get("SubAccount", False)]
        created_count = 0
        skipped_count = 0

        print(f"\n=== PASS 1: Creating {len(parent_accounts)} parent accounts ===")
        print(f"Identified {len(parent_ids_with_children)} accounts that need to be groups")

        for acc in parent_accounts:
            # Check if this account is a parent to any sub-accounts
            is_parent = acc.get("Id") in parent_ids_with_children
            result = create_account(acc, company, is_parent=is_parent)
            if result == "created":
                created_count += 1
            else:
                skipped_count += 1

        # Second pass: Create sub-accounts
        sub_accounts = [acc for acc in accounts if acc.get("SubAccount", False)]
        print(f"\n=== PASS 2: Creating {len(sub_accounts)} sub-accounts ===")
        for acc in sub_accounts:
            result = create_account(acc, company, is_parent=False)
            if result == "created":
                created_count += 1
            else:
                skipped_count += 1

        summary = f"✅ Sync Complete! Created: {created_count}, Skipped: {skipped_count}, Total: {len(accounts)}"
        print(f"\n{summary}")
        return summary

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks COA Sync Error")
        return f"Error: {str(e)}"


def create_account(acc, company, is_parent=False):
    """Create a single account in ERPNext"""
    acc_name = acc.get("Name")
    acc_type = acc.get("AccountType")
    acc_subtype = acc.get("AccountSubType")
    acc_id = acc.get("Id")
    acc_number = acc.get("AcctNum") or f"QB{acc_id}"  # Store QB ID in account number
    parent_id = acc.get("ParentRef", {}).get("value")
    is_sub_account = acc.get("SubAccount", False)
    currency = acc.get("CurrencyRef", {}).get("value", "NGN")
    is_active = acc.get("Active", True)
    fully_qualified_name = acc.get("FullyQualifiedName", acc_name)

    # Check if account already exists by account number (which contains QB ID)
    existing = frappe.db.exists("Account", {
        "account_number": acc_number,
        "company": company
    })
    if existing:
        print(f"⏭️  Skipping {acc_name} - already exists ({acc_number})")
        return "skipped"

    # Also check by name to avoid duplicates
    existing_by_name = frappe.db.exists("Account", {
        "account_name": acc_name,
        "company": company
    })
    if existing_by_name:
        print(f"⏭️  Skipping {acc_name} - account with same name exists")
        return "skipped"

    # Map QuickBooks account type to ERPNext
    account_type, root_type = map_quickbooks_type(acc_type, acc_subtype)

    if not account_type or not root_type:
        print(f"⏭️  Skipping {acc_name} - unknown account type: {acc_type}")
        return "skipped"

    # Determine parent account
    parent_account = None
    if is_sub_account and parent_id:
        # Sub-accounts have a parent - find by QB parent ID
        parent_acc_num = f"QB{parent_id}"
        parent_account = frappe.db.get_value("Account", {
            "account_number": parent_acc_num,
            "company": company
        }, "name")
        if not parent_account:
            print(f"⏭️  Skipping sub-account {acc_name} - parent QB{parent_id} not found")
            return "skipped"
    else:
        # Root accounts should be under ERPNext root groups
        parent_account = get_default_root_account(root_type, company)

    if not parent_account:
        print(f"⏭️  Skipping {acc_name} - no valid parent found")
        return "skipped"

    # Determine if this should be a group account
    # Accounts with children must be groups, others are leaf accounts
    is_group = 1 if is_parent else 0

    try:
        account_doc = {
            "doctype": "Account",
            "account_name": acc_name,
            "account_number": acc_number,
            "parent_account": parent_account,
            "is_group": is_group,
            "company": company,
            "account_currency": currency,
            "disabled": 0 if is_active else 1
        }

        # Only set account_type for leaf accounts (non-group accounts)
        # Group accounts should not have account_type set
        if account_type and not is_group:
            account_doc["account_type"] = account_type

        new_account = frappe.get_doc(account_doc)
        new_account.insert(ignore_permissions=True)
        frappe.db.commit()

        group_str = "[GROUP]" if is_group else f"[Type: {account_type}]"
        print(f"✅ Created: {acc_name} ({acc_number}) {group_str} under {parent_account}")
        return "created"
    except Exception as e:
        print(f"❌ Failed to create {acc_name}: {str(e)}")
        frappe.log_error(frappe.get_traceback(), f"Account Creation Error - {acc_name}")
        return "failed"


def get_default_root_account(root_type, company):
    """Map root_type to ERPNext's default root group accounts"""
    # Query by root_type instead of hardcoded names, as different companies have different root account names
    return frappe.db.get_value("Account", {
        "root_type": root_type,
        "company": company,
        "is_group": 1,
        "parent_account": ["is", "not set"]
    }, "name")


def map_quickbooks_type(acc_type, acc_subtype):
    """Map QuickBooks AccountType to ERPNext account_type and root_type"""
    mapping = {
        "Accounts Receivable": ("Receivable", "Asset"),
        "Accounts Payable": ("Payable", "Liability"),
        "Bank": ("Bank", "Asset"),
        "Credit Card": ("Liability", "Liability"),  # ERPNext doesn't have "Credit Card" type
        "Fixed Asset": ("Fixed Asset", "Asset"),
        "Other Asset": ("Fixed Asset", "Asset"),  # Map to Fixed Asset or leave as none
        "Other Current Asset": ("Current Asset", "Asset"),
        "Other Current Liability": ("Current Liability", "Liability"),
        "Long Term Liability": ("Liability", "Liability"),  # ERPNext doesn't have separate "Long Term Liability"
        "Equity": ("Equity", "Equity"),
        "Income": ("Income Account", "Income"),
        "Other Income": ("Income Account", "Income"),
        "Expense": ("Expense Account", "Expense"),
        "Other Expense": ("Expense Account", "Expense"),
        "Cost of Goods Sold": ("Cost of Goods Sold", "Expense")
    }
    return mapping.get(acc_type, (None, None))

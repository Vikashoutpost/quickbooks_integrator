import frappe
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
import traceback
import requests
import json


@frappe.whitelist()
def get_auth_url():
    settings = frappe.get_single("Quickbook Settings")

    client_id = settings.client_id
    client_secret = settings.client_secret
    redirect_uri = settings.redirect_uri
    environment = settings.environment or "sandbox"

    if not client_id:
        frappe.throw("Client ID is missing in Quickbook Settings")
    if not client_secret:
        frappe.throw("Client Secret is missing in Quickbook Settings")
    if not redirect_uri:
        frappe.throw("Redirect URI is missing in Quickbook Settings")

    print("🔐 QuickBooks OAuth Client Details:")
    print("Client ID:", client_id)
    print("Client Secret:", client_secret)
    print("Redirect URI:", redirect_uri)
    print("Environment:", environment)

    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        redirect_uri=redirect_uri
    )

    scopes = [Scopes.ACCOUNTING]
    auth_url = auth_client.get_authorization_url(scopes)

    print("🌐 Generated QuickBooks OAuth URL:", auth_url)

    frappe.cache().set_value("quickbooks_auth_client", auth_client)

    return auth_url


@frappe.whitelist(allow_guest=True)
def oauth_callback(code=None, state=None, realmId=None):
    print("🔁 QuickBooks OAuth Callback:")
    print("Code:", code)
    print("Realm ID:", realmId)

    if not code:
        frappe.throw("Missing authorization code from QuickBooks.")

    try:
        settings = frappe.get_single("Quickbook Settings")

        client_id = settings.client_id
        client_secret = settings.client_secret
        redirect_uri = settings.redirect_uri
        environment = settings.environment or "sandbox"

        if not client_id or not client_secret or not redirect_uri:
            frappe.throw("Missing QuickBooks configuration in settings.")

        auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            environment=environment,
            redirect_uri=redirect_uri
        )

        print("🔐 Requesting token from QuickBooks...")

        auth_client.get_bearer_token(code, realm_id=realmId)

        # Save tokens & realmId from auth_client attributes
        settings.refresh_token = auth_client.refresh_token
        settings.access_token = auth_client.access_token
        settings.realm_id = realmId
        settings.save(ignore_permissions=True)

        print("✅ QuickBooks token saved successfully:")
        print("Access Token:", settings.access_token)
        print("Refresh Token:", settings.refresh_token)
        print("Realm ID:", settings.realm_id)

        # 🔹 Fetch Company Info
        company_info_url = f"https://quickbooks.api.intuit.com/v3/company/{realmId}/companyinfo/{realmId}"
        headers = {
            "Authorization": f"Bearer {settings.access_token}",
            "Accept": "application/json"
        }

        response = requests.get(company_info_url, headers=headers)
        company_info = response.json()

        print("🏢 Company Info:")
        print(json.dumps(company_info, indent=2))

        # Optionally store company name in settings
        if company_info.get("CompanyInfo"):
            settings.company_name = company_info["CompanyInfo"].get("CompanyName")
            settings.save(ignore_permissions=True)

        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/quickbook-settings"
        return "QuickBooks connection successful"

    except AuthClientError as e:
        print("❌ AuthClientError during token exchange:")
        traceback.print_exc()
        frappe.throw(f"QuickBooks OAuth failed: {e.content}")

    except Exception as e:
        print("❌ Exception during token exchange or company info fetch:")
        traceback.print_exc()
        frappe.throw(f"QuickBooks authorization failed: {e}")

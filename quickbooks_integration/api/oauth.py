import frappe
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import traceback
import requests
import json
from datetime import datetime, timedelta


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

        # Exchange authorization code for tokens
        auth_client.get_bearer_token(auth_code=code, realm_id=realmId)


        if not auth_client.access_token:
            frappe.throw("Failed to retrieve access token from QuickBooks.")

        # Save tokens & realmId
        settings.refresh_token = auth_client.refresh_token
        settings.access_token = auth_client.access_token
        settings.realm_id = realmId
        settings.save(ignore_permissions=True)

        print("✅ QuickBooks token saved successfully:")
        print("Access Token:", settings.access_token)
        print("Refresh Token:", settings.refresh_token)
        print("Realm ID:", settings.realm_id)

        frappe.db.commit()
        # Redirect to Quickbook Settings page
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/quickbook-settings"

    except Exception as e:
        print("❌ Exception during token exchange or company info fetch:")
        traceback.print_exc()
        frappe.throw(f"QuickBooks authorization failed: {e}")

import frappe
import requests
import json
from frappe.utils import nowdate

@frappe.whitelist()
def sync_quickbooks_payments():
    try:
        # Load QuickBooks Settings
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        # Choose base URL
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        
        # Query for all Payments
        query = "SELECT * FROM Payment"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        print(f"📡 Sending request to: {endpoint} with Query: {query}")
        response = requests.post(endpoint, headers=headers, data=query)

        if response.status_code != 200:
            print(f"❌ Failed to fetch payments: {response.text}")
            return f"Failed to fetch payments: {response.text}"

        payment_data = response.json()
        payments = payment_data.get("QueryResponse", {}).get("Payment", [])
        print("🔎 Raw Payment Response:")
        print(json.dumps(payments, indent=4))

        if not payments:
            return "No payments found in QuickBooks."

        synced_count = 0
        company = frappe.defaults.get_global_default("company")
        company_currency = frappe.get_cached_value("Company", company, "default_currency")

        for qb_payment in payments:
            try:
                qb_payment_id = qb_payment.get("Id")
                amount = qb_payment.get("TotalAmt", 0)
                txn_date = qb_payment.get("TxnDate", nowdate())
                customer_ref = qb_payment.get("CustomerRef", {}).get("value")
                customer_name = qb_payment.get("CustomerRef", {}).get("name", "Unknown Customer")

                print(f"\n➡️ Processing Payment: {qb_payment_id}, Amount: {amount}, CustomerRef: {customer_ref}, Name: {customer_name}")

                # Skip invalid/zero payments
                if not amount or float(amount) <= 0:
                    print(f"⚠️ Skipping payment {qb_payment_id} because amount is {amount}")
                    continue

                # ✅ Find ERPNext customer using QuickBooks Customer Id
                erp_customer = frappe.db.get_value(
                    "Customer",
                    {"custom_quickbooks_customer_id": customer_ref},  # custom field match
                    "name"
                )

                if not erp_customer:
                    print(f"❌ Could not find ERPNext Customer for QuickBooks ID {customer_ref} ({customer_name})")
                    continue

                print(f"✅ Found ERPNext Customer: {erp_customer} for QuickBooks ID {customer_ref}")

                # ✅ Check if already synced
                if frappe.db.exists("Payment Entry", {"qbo_payment_id": qb_payment_id}):
                    print(f"⚠️ Payment {qb_payment_id} already synced. Skipping.")
                    continue

                # Get default accounts
                receivable_account = frappe.get_cached_value("Company", company, "default_receivable_account")
                bank_account = "119010 - FCMB Bank - MTL"

                # ✅ Create new Payment Entry (always company currency)
                pe = frappe.new_doc("Payment Entry")
                pe.payment_type = "Receive"
                pe.company = company
                pe.party_type = "Customer"
                pe.party = erp_customer
                pe.posting_date = txn_date
                pe.mode_of_payment = "Cash"  # TODO: Map properly if you want
                pe.paid_amount = amount
                pe.received_amount = amount
                pe.reference_no = qb_payment_id
                pe.reference_date = txn_date
                pe.qbo_payment_id = qb_payment_id  # custom field in Payment Entry

                # Accounts
                pe.paid_from = receivable_account
                pe.paid_to = bank_account
                pe.paid_from_account_currency = company_currency
                pe.paid_to_account_currency = company_currency

                # ✅ Add required defaults
                pe.cost_center = "Benin - MTL"
                pe.channel = "Logistics - MDC"
                pe.department = "Operations - MTL"

                # Force exchange rates (ERPNext default currency only)
                pe.source_exchange_rate = 1
                pe.target_exchange_rate = 1

                pe.save(ignore_permissions=True)
                pe.submit()

                print(f"✅ Synced Payment Entry: {qb_payment_id} ({amount}) for {erp_customer}")
                synced_count += 1
                print(f"Total Synced Count: {synced_count}")
                print("-" * 50)

            except Exception as pe_err:
                frappe.log_error(frappe.get_traceback(), f"Payment Sync Failed: {qb_payment.get('Id')}")
                print(f"❌ Error syncing payment {qb_payment.get('Id')}: {pe_err}")

        return f"✅ Synced {synced_count} Payment Entry records from QuickBooks."

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Payment Sync Error")
        return f"🔥 Error occurred: {str(e)}"

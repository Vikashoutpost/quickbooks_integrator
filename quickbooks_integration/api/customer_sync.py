import frappe
import requests
import json

def get_or_create_payment_terms_template(template_name="3 Days from Invoice Date"):
    """Ensure a Payment Terms Template exists and return its name"""
    if frappe.db.exists("Payment Terms Template", template_name):
        return template_name
    else:
        pt = frappe.new_doc("Payment Terms Template")
        pt.payment_terms_template_name = template_name
        pt.append("terms", {
            "term_type": "Net",
            "due_after": 3,
            "description": "Payment due in 3 days from invoice date"
        })
        pt.save(ignore_permissions=True)
        return template_name


@frappe.whitelist()
def sync_quickbooks_customers():
    try:
        # Get QuickBooks Settings
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access token or Realm ID is missing. Please connect to QuickBooks.")

        # Get default company
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            frappe.throw("No default company set in Global Defaults. Please configure it first.")

        # Get company's default receivable account
        default_receivable_account = frappe.get_value(
            "Company", default_company, "default_receivable_account"
        )
        if not default_receivable_account:
            frappe.throw(f"No default receivable account set for company {default_company}.")

        # Ensure default payment terms exist
        default_terms = get_or_create_payment_terms_template("3 Days from Invoice Date")

        # Define QuickBooks endpoint
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = "select * from Customer"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        response = requests.post(endpoint, headers=headers, data=query)
        if response.status_code != 200:
            frappe.throw(f"Failed to fetch customers from QuickBooks: {response.text}")

        customer_data = response.json()
        customers = customer_data.get("QueryResponse", {}).get("Customer", [])
        print("Fetched Customers:", json.dumps(customers, indent=2))
        print(f"🔥 Total Customers in QuickBooks: {len(customers)}")

        if not customers:
            return "No customers found in QuickBooks."

        created_customers = []
        skipped_customers = []

        for cust in customers:
            qb_customer_id = cust.get("Id")
            cust_name = cust.get("DisplayName")

            if not cust_name:
                continue

            # Check if already exists by QuickBooks ID
            if frappe.db.exists("Customer", {"custom_quickbooks_customer_id": qb_customer_id}):
                skipped_customers.append(cust_name)
                continue

            # Check if already exists by Name (fallback)
            if frappe.db.exists("Customer", {"customer_name": cust_name}):
                skipped_customers.append(cust_name)
                continue

            email = (cust.get("PrimaryEmailAddr") or {}).get("Address")
            phone = (cust.get("PrimaryPhone") or {}).get("FreeFormNumber")

            customer_doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cust_name,
                "customer_type": "Individual" if cust.get("CompanyName") is None else "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
                "default_currency": "NGN",
                "payment_terms": default_terms,
                "custom_quickbooks_customer_id": qb_customer_id,
                "accounts": [
                    {
                        "company": default_company,
                        "account": default_receivable_account
                    }
                ],
                "email_id": email or "",
                "phone": phone or ""
            })

            customer_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            created_customers.append(cust_name)
            print(f"Created Customer: {cust_name}")
            print(f"🔥 Total Created Customers: {len(created_customers)}")

        return {
            "created_customers": created_customers,
            "skipped_customers": skipped_customers
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Customer Sync Error")
        return f"Error occurred: {str(e)}"

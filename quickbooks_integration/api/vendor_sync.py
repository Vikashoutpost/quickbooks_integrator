import frappe
import requests
import json

@frappe.whitelist()
def sync_quickbooks_vendors():
    try:
        # Load QuickBooks settings
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        # Determine QuickBooks base URL
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = "SELECT * FROM Vendor"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        response = requests.post(endpoint, headers=headers, data=query)

        if response.status_code != 200:
            frappe.log_error(response.text, "QuickBooks Vendor Sync API Error")
            return "Failed to fetch vendors. Check error logs."

        vendor_data = response.json()
        vendors = vendor_data.get("QueryResponse", {}).get("Vendor", [])
        print("Fetched Vendors:", json.dumps(vendors, indent=2))  # Debugging output
        print("Fetched Vendors Count:", len(vendors))

        if not vendors:
            return "No vendors found in QuickBooks."

        created, updated = 0, 0

        # Get default company
        default_company = frappe.defaults.get_user_default("Company")

        # Get company's default currency
        company_currency = frappe.db.get_value("Company", default_company, "default_currency")

        # Try fetching default payable account from Company
        default_payable = frappe.db.get_value("Company", default_company, "default_payable_account")

        # If not found, fallback to your fixed account
        if not default_payable:
            default_payable = frappe.db.get_value(
                "Account",
                {"name": "226040 - Other Creditors - NGN - MTL"},
                "name"
            )

        if not default_payable:
            frappe.throw("No default payable account found. Please set it in Company or check the fallback account.")

        for v in vendors:
            vendor_name = v.get("DisplayName")
            email = v.get("PrimaryEmailAddr", {}).get("Address")
            phone = v.get("PrimaryPhone", {}).get("FreeFormNumber")
            company_name = v.get("CompanyName") or vendor_name
            qb_id = v.get("Id")

            if not vendor_name:
                continue  # skip if vendor has no name

            # Check if supplier already exists (using QuickBooks Id as unique key)
            existing_supplier = frappe.db.exists("Supplier", {"custom_quickbooks_vendor_id": qb_id})

            if existing_supplier:
                supplier = frappe.get_doc("Supplier", existing_supplier)
                supplier.supplier_name = vendor_name
                supplier.supplier_group = supplier.supplier_group or "All Supplier Groups"
                supplier.supplier_type = supplier.supplier_type or "Company"
                supplier.supplier_email = email
                supplier.mobile_no = phone
                supplier.company_name = company_name

                # ✅ Always match ERPNext company currency
                supplier.default_currency = company_currency

                # Always ensure accounts row exists
                supplier.set("accounts", [{
                    "company": default_company,
                    "account": default_payable
                }])

                supplier.save(ignore_permissions=True)
                updated += 1
            else:
                supplier = frappe.get_doc({
                    "doctype": "Supplier",
                    "supplier_name": vendor_name,
                    "supplier_group": "All Supplier Groups",
                    "supplier_type": "Company",
                    "supplier_email": email,
                    "mobile_no": phone,
                    "company_name": company_name,
                    "custom_quickbooks_vendor_id": qb_id,  # custom field you should add

                    # ✅ Force company currency as billing currency
                    "default_currency": company_currency,

                    "accounts": [{
                        "company": default_company,
                        "account": default_payable
                    }]
                })
                supplier.insert(ignore_permissions=True)
                created += 1

        frappe.db.commit()

        return f"✅ Vendor Sync Completed: {created} created, {updated} updated."
        print(f"Created Suppliers: {created}")
        print(f"Updated Suppliers: {updated}")
        print(f"Skipped Suppliers: {len(vendors) - (created + updated)}")
        print(f"Total Suppliers Processed: {len(vendors)}")
        print(f"Vendor Sync Completed Successfully")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Vendor Sync Error")
        return f"🔥 Error occurred: {str(e)}"

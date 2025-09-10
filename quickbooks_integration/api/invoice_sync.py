import frappe
import requests
import json
from frappe.utils import nowdate
from frappe import _   # ✅ Fix for translation function


def get_or_create_payment_terms_template(template_name="3 Days from Invoice Date"):
    """Ensure a Payment Terms Template exists and return its name"""
    if frappe.db.exists("Payment Terms Template", template_name):
        return template_name
    else:
        pt = frappe.new_doc("Payment Terms Template")
        pt.payment_terms_template_name = template_name
        # Add a default term of 3 days
        pt.append("terms", {
            "term_type": "Net",
            "due_after": 3,
            "description": "Payment due in 3 days from invoice date"
        })
        pt.save(ignore_permissions=True)
        return template_name


@frappe.whitelist()
def sync_quickbooks_invoices():
    """Sync invoices from QuickBooks to ERPNext"""
    try:
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("QuickBooks access token or Realm ID is missing. Please check Quickbook Settings.")

        base_url = (
            "https://sandbox-quickbooks.api.intuit.com"
            if environment == "sandbox"
            else "https://quickbooks.api.intuit.com"
        )

        # Fetch invoices
        url = f"{base_url}/v3/company/{realm_id}/query"
        query = {"query": "SELECT * FROM Invoice MAXRESULTS 50", "minorversion": "65"}
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text",
        }

        response = requests.post(url, headers=headers, data=query["query"])
        data = response.json()
        invoices = data.get("QueryResponse", {}).get("Invoice", [])
        frappe.msgprint(f"🔥 Total Invoices in QuickBooks: {len(invoices)}")
        print("Fetched Invoices:", json.dumps(invoices, indent=2))
        print(f"🔥 Total Invoices in QuickBooks: {len(invoices)}")

        created_invoices = []
        skipped_invoices = []

        # Ensure payment terms template exists
        default_terms = get_or_create_payment_terms_template("3 Days from Invoice Date")

        # ✅ Fixed Cost Center
        fixed_cost_center = "Benin - MTL"

        for qb_invoice in invoices:
            try:
                qb_invoice_id = qb_invoice.get("Id")
                customer_ref = qb_invoice.get("CustomerRef", {}).get("name")

                if not customer_ref:
                    skipped_invoices.append(f"Invoice {qb_invoice_id} → No CustomerRef in QuickBooks")
                    continue

                # ✅ Lookup customer by customer_name or name
                customer_name = frappe.db.get_value("Customer", {"customer_name": customer_ref}, "name") \
                                or frappe.db.get_value("Customer", {"name": customer_ref}, "name")

                if not customer_name:
                    skipped_invoices.append(f"Invoice {qb_invoice_id} → Customer '{customer_ref}' not found in ERPNext")
                    continue

                customer = frappe.get_doc("Customer", customer_name)

                # ✅ Ensure customer has payment terms
                if not customer.payment_terms:
                    customer.payment_terms = default_terms
                    customer.save(ignore_permissions=True)

                # Skip if invoice already exists
                if frappe.db.exists("Sales Invoice", {"custom_quickbooks_invoice_id": qb_invoice_id}):
                    skipped_invoices.append(f"Invoice {qb_invoice_id} → Already exists in ERPNext")
                    continue

                # Create Sales Invoice
                si = frappe.new_doc("Sales Invoice")
                si.customer = customer.name
                si.company = frappe.defaults.get_user_default("Company")
                si.posting_date = qb_invoice.get("TxnDate") or nowdate()
                si.custom_quickbooks_invoice_id = qb_invoice_id  # ✅ mapped to custom field
                si.payment_terms_template = customer.payment_terms or default_terms
                si.currency = frappe.get_cached_value("Company", si.company, "default_currency")  # ✅ Fix billing currency issue

                # ✅ Map Header Cost Center
                si.cost_center = fixed_cost_center

                # ✅ Skip SO/DN validation if coming from QuickBooks
                si.flags.ignore_mandatory = True

                # Add items
                for line in qb_invoice.get("Line", []):
                    detail = line.get("SalesItemLineDetail")
                    if not detail:
                        continue

                    item_ref = detail.get("ItemRef", {}).get("name")
                    if not item_ref:
                        continue

                    # Lookup item code
                    item_code = frappe.db.get_value("Item", {"item_code": item_ref}, "item_code") \
                                or frappe.db.get_value("Item", {"item_name": item_ref}, "item_code")

                    if not item_code:
                        skipped_invoices.append(f"Invoice {qb_invoice_id} → Item '{item_ref}' not found")
                        continue

                    qty = detail.get("Qty", 1)
                    amount = line.get("Amount", 0)
                    rate = amount / qty if qty else 0

                    si.append("items", {
                        "item_code": item_code,
                        "qty": qty,
                        "rate": rate,
                        "amount": amount,
                        "cost_center": fixed_cost_center   # ✅ Line-level cost center
                    })

                # Save and submit
                si.save(ignore_permissions=True)
                si.submit()
                created_invoices.append(f"Invoice {qb_invoice_id} → Created for Customer '{customer_ref}'")
                frappe.msgprint(f"Invoice {qb_invoice_id} → Created for Customer '{customer_ref}'")
                print(f"Invoice {qb_invoice_id} → Created for Customer '{customer_ref}'")

            except Exception:
                skipped_invoices.append(f"Invoice {qb_invoice.get('Id')} → Error: {frappe.get_traceback()}")
                print(f"Error processing Invoice {qb_invoice.get('Id')}: {frappe.get_traceback()}")

        # Summary
        summary = "<b>✅ Created Invoices:</b><br>" + "<br>".join(created_invoices) if created_invoices else "None"
        summary += "<br><br><b>❌ Skipped Invoices:</b><br>" + "<br>".join(skipped_invoices) if skipped_invoices else ""
        frappe.msgprint(summary)
        print(summary)

    except Exception as e:
        frappe.throw(f"Error syncing invoices: {str(e)}")

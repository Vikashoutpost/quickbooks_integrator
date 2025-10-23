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

        # Fetch invoices with pagination
        url = f"{base_url}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text",
        }

        # Fetch all invoices with pagination (QB API returns max 1000 records per request)
        all_invoices = []
        start_position = 1
        max_results = 1000

        print(f"📡 Fetching invoices from QuickBooks...")

        while True:
            query = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}"
            print(f"   Query: {query}")

            response = requests.post(url, headers=headers, data=query)

            # ✅ Check for API errors
            if response.status_code == 401:
                frappe.throw("Unauthorized: Token expired or invalid. Please reconnect QuickBooks.")
            elif response.status_code == 403:
                frappe.throw("Forbidden: Access denied by QuickBooks. Check your app permissions.")
            elif response.status_code != 200:
                print(f"❌ QuickBooks API Error: {response.status_code}")
                print(f"Response: {response.text}")
                frappe.throw(f"QuickBooks API Error: {response.status_code}, {response.text}")

            data = response.json()
            invoices_batch = data.get("QueryResponse", {}).get("Invoice", [])

            if not invoices_batch:
                break

            all_invoices.extend(invoices_batch)
            print(f"   Fetched {len(invoices_batch)} invoices (Total so far: {len(all_invoices)})")

            # If we got less than max_results, we've reached the end
            if len(invoices_batch) < max_results:
                break

            start_position += max_results

        invoices = all_invoices
        print(f"\n📊 Total Invoices Fetched: {len(invoices)}")
        frappe.msgprint(f"🔥 Total Invoices in QuickBooks: {len(invoices)}")

        created_invoices = []
        skipped_invoices = []

        # Ensure payment terms template exists
        default_terms = get_or_create_payment_terms_template("3 Days from Invoice Date")

        # ✅ Fixed Cost Center
        fixed_cost_center = "Benin - MTL"

        for qb_invoice in invoices:
            try:
                # ✅ Log the full JSON structure from QuickBooks
                print(f"\n{'='*80}")
                print(f"RAW QUICKBOOKS INVOICE DATA (JSON):")
                print(f"{'='*80}")
                print(json.dumps(qb_invoice, indent=2))
                print(f"{'='*80}\n")

                qb_invoice_id = qb_invoice.get("Id")
                qb_doc_number = qb_invoice.get("DocNumber")  # User-visible invoice number like "MOV/003"
                customer_ref = qb_invoice.get("CustomerRef", {}).get("name")

                print(f"\n➡️  Processing Invoice {qb_invoice_id} for Customer: {customer_ref}")
                print(f"   🔑 Internal ID: {qb_invoice_id}")
                print(f"   📄 DocNumber: {qb_doc_number}")
                print(f"   DocNumber will be stored in: custom_quickbooks_invoice_id")

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

                # Skip if invoice already exists (check by DocNumber)
                if frappe.db.exists("Sales Invoice", {"custom_quickbooks_invoice_id": qb_doc_number}):
                    skipped_invoices.append(f"Invoice {qb_doc_number} (QB ID: {qb_invoice_id}) → Already exists in ERPNext")
                    continue

                # Get default company
                company = frappe.db.get_single_value("Global Defaults", "default_company")
                if not company:
                    frappe.throw("No default company set in Global Defaults.")

                # ✅ Get currency from QuickBooks invoice or customer's default currency
                qb_currency = qb_invoice.get("CurrencyRef", {}).get("value")
                customer_currency = frappe.get_cached_value("Customer", customer.name, "default_currency")
                invoice_currency = qb_currency or customer_currency or frappe.get_cached_value("Company", company, "default_currency")

                # Create Sales Invoice
                si = frappe.new_doc("Sales Invoice")
                si.customer = customer.name
                si.company = company
                si.posting_date = qb_invoice.get("TxnDate") or nowdate()
                si.custom_quickbooks_invoice_id = qb_doc_number  # ✅ Store DocNumber (e.g., "MOV/003") instead of internal ID
                si.payment_terms_template = customer.payment_terms or default_terms
                si.currency = invoice_currency  # ✅ Use QB currency or customer's currency

                # ✅ Map Header Cost Center
                si.cost_center = fixed_cost_center

                # ✅ Skip SO/DN validation if coming from QuickBooks
                si.flags.ignore_mandatory = True

                items_added = 0
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
                        print(f"   ⏭️  Skipping line item '{item_ref}' - not found in ERPNext")
                        continue

                    qty = detail.get("Qty", 1)
                    amount = line.get("Amount", 0)
                    rate = amount / qty if qty else 0

                    # ✅ Get item's default UOM
                    item_uom = frappe.get_cached_value("Item", item_code, "stock_uom")

                    # ✅ Check if UOM must be whole number
                    uom_must_be_whole = frappe.db.get_value("UOM", item_uom, "must_be_whole_number")

                    # If fractional qty but UOM requires whole number, adjust to use amount-based pricing
                    if uom_must_be_whole and qty != int(qty):
                        print(f"   ⚠️  Item {item_code} has fractional qty {qty} but UOM '{item_uom}' requires whole numbers")
                        print(f"   💡 Converting to qty=1, rate={amount}")
                        qty = 1
                        rate = amount

                    si.append("items", {
                        "item_code": item_code,
                        "qty": qty,
                        "rate": rate,
                        "uom": item_uom,
                        "amount": amount,
                        "cost_center": fixed_cost_center   # ✅ Line-level cost center
                    })
                    items_added += 1

                # Skip invoice if no items were added
                if items_added == 0:
                    print(f"⏭️  Skipping Invoice {qb_invoice_id} - no valid items found")
                    skipped_invoices.append(f"Invoice {qb_invoice_id} → No valid items found")
                    continue

                # Save and submit
                si.save(ignore_permissions=True)
                si.submit()

                print(f"✅ Created Sales Invoice: {si.name} (SUBMITTED) for QB Invoice {qb_invoice_id}")
                print(f"   Customer: {customer_ref} | Currency: {invoice_currency} | Items: {items_added} | Total: {si.grand_total}")

                created_invoices.append(f"Invoice {qb_invoice_id} → {si.name} (Customer: {customer_ref}, Total: {si.grand_total} {invoice_currency})")
                frappe.msgprint(f"✅ Created: {si.name} for QB Invoice {qb_invoice_id}")

            except Exception as e:
                error_msg = str(e)
                skipped_invoices.append(f"Invoice {qb_invoice.get('Id')} → Error: {error_msg}")
                print(f"❌ Error processing Invoice {qb_invoice.get('Id')}: {error_msg}")
                frappe.log_error(frappe.get_traceback(), f"Invoice Sync Failed: {qb_invoice.get('Id')}")

        # Summary
        print(f"\n{'='*60}")
        print(f"📊 INVOICE SYNC SUMMARY")
        print(f"{'='*60}")
        print(f"Total Invoices in QuickBooks: {len(invoices)}")
        print(f"✅ Successfully Created: {len(created_invoices)}")
        print(f"⏭️  Skipped: {len(skipped_invoices)}")
        print(f"{'='*60}\n")

        summary = f"<b>📊 Invoice Sync Complete!</b><br><br>"
        if created_invoices:
            summary += f"<b>✅ Created: {len(created_invoices)}</b><br>" + "<br>".join(created_invoices)
        else:
            summary += "<b>✅ Created: 0</b><br>None"

        if skipped_invoices:
            summary += f"<br><br><b>⏭️  Skipped: {len(skipped_invoices)}</b><br>" + "<br>".join(skipped_invoices)

        frappe.msgprint(summary)

        return {
            "message": f"Invoice Sync Complete! Created: {len(created_invoices)}, Skipped: {len(skipped_invoices)}, Total: {len(invoices)}",
            "created": len(created_invoices),
            "skipped": len(skipped_invoices),
            "total": len(invoices)
        }

    except Exception as e:
        frappe.throw(f"Error syncing invoices: {str(e)}")

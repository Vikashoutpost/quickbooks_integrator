import frappe
import requests
import json

@frappe.whitelist()
def sync_quickbooks_items():
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
        query = "SELECT * FROM Item"  # Fetch all items

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        response = requests.post(endpoint, headers=headers, data=query)

        if response.status_code != 200:
            frappe.log_error(response.text, "QuickBooks Item Fetch Error")
            return "Failed to fetch items. Check error logs."

        item_data = response.json()
        print("Fetched Item Data:", json.dumps(item_data, indent=2))
        print("Fetched Items Count:", len(item_data.get("QueryResponse", {}).get("Item", [])))

        if "QueryResponse" not in item_data or "Item" not in item_data["QueryResponse"]:
            return "No items found in QuickBooks."

        qb_items = item_data["QueryResponse"]["Item"]

        created_items = []
        skipped_items = []

        for qb_item in qb_items:
            try:
                # Map QuickBooks fields to ERPNext fields
                qb_item_id = qb_item.get("Id")
                item_code = qb_item.get("Name") or qb_item_id
                item_name = qb_item.get("FullyQualifiedName") or qb_item.get("Name")
                description = qb_item.get("Description", "")
                is_stock_item = qb_item.get("Type") == "Inventory"

                # ✅ Dynamic Item Group
                qb_item_group = qb_item.get("SubItem") or "All Item Groups"
                if not frappe.db.exists("Item Group", qb_item_group):
                    # create item group if not exists
                    ig = frappe.get_doc({
                        "doctype": "Item Group",
                        "item_group_name": qb_item_group,
                        "parent_item_group": "All Item Groups",
                        "is_group": 0
                    })
                    ig.insert(ignore_permissions=True)
                    frappe.db.commit()

                # ✅ Dynamic UOM
                qb_uom = qb_item.get("UnitPrice")  # QB does not always store UOM directly
                stock_uom = qb_item.get("Unit") or "Nos"
                if not frappe.db.exists("UOM", stock_uom):
                    uom_doc = frappe.get_doc({"doctype": "UOM", "uom_name": stock_uom})
                    uom_doc.insert(ignore_permissions=True)
                    frappe.db.commit()

                # Check if item already exists by QuickBooks ID
                existing_item = frappe.db.exists("Item", {"custom_quickbooks_item_id": qb_item_id})
                if existing_item:
                    # ✅ Update existing item instead of skipping
                    erp_item = frappe.get_doc("Item", existing_item)
                    erp_item.item_name = item_name
                    erp_item.description = description
                    erp_item.item_group = qb_item_group
                    erp_item.stock_uom = stock_uom
                    erp_item.is_stock_item = 1 if is_stock_item else 0
                    erp_item.save(ignore_permissions=True)
                    frappe.db.commit()
                    skipped_items.append(item_code)
                    continue

                # Create new ERPNext Item
                erp_item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_name,
                    "item_group": qb_item_group,
                    "description": description,
                    "stock_uom": stock_uom,
                    "is_stock_item": 1 if is_stock_item else 0,
                    "disabled": 0,
                    "custom_quickbooks_item_id": qb_item_id
                })
                erp_item.insert(ignore_permissions=True)
                frappe.db.commit()

                created_items.append(item_code)

            except Exception:
                frappe.log_error(frappe.get_traceback(), "QuickBooks Item Creation Error")
                skipped_items.append(qb_item.get("Name") or qb_item.get("Id"))

        return f"✅ Sync complete. Created: {len(created_items)} | Updated/Skipped: {len(skipped_items)}"
        print(f"Created Items: {created_items}")
        print(f"Skipped Items: {skipped_items}")    

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Item Sync Error")
        return f"Error occurred: {str(e)}"
        print(f"Error syncing items: {str(e)}")
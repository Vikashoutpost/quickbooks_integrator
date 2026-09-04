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

        from quickbooks_integration.api.account_mapper import resolve_account_master
        company = "Movam Technologies Limited"

        for qb_item in qb_items:
            try:
                # Map QuickBooks fields to ERPNext fields
                qb_item_id = qb_item.get("Id")
                item_code = qb_item.get("Name") or qb_item_id
                item_name = qb_item.get("FullyQualifiedName") or qb_item.get("Name")
                description = qb_item.get("Description", "")
                is_stock_item = qb_item.get("Type") == "Inventory"

                # Extract account refs from QBO
                income_ref = qb_item.get("IncomeAccountRef") or {}
                expense_ref = qb_item.get("ExpenseAccountRef") or {}
                resolved_income = None
                resolved_expense = None

                if income_ref:
                    resolved_income = resolve_account_master(
                        company=company,
                        qb_account_id=income_ref.get("value"),
                        qb_account_name=income_ref.get("name")
                    )
                if expense_ref:
                    resolved_expense = resolve_account_master(
                        company=company,
                        qb_account_id=expense_ref.get("value"),
                        qb_account_name=expense_ref.get("name")
                    )

                # Intelligent fallbacks if not resolved
                if not resolved_income:
                    lower_name = (item_name or "").lower()
                    if any(k in lower_name for k in ["logistic", "delivery", "mdc delivery"]):
                        resolved_income = "311020 - Revenue - Logistics - MTL"
                    elif any(k in lower_name for k in ["tracker", "device", "teltonika"]):
                        resolved_income = "311030 - Revenue - Device - MTL"
                    else:
                        resolved_income = "311010 - Revenue - SAAS - MTL"

                if not resolved_expense:
                    lower_name = (item_name or "").lower()
                    if any(k in lower_name for k in ["tracker", "device", "teltonika", "hardware", "gps"]):
                        resolved_expense = "401040 - COGS Device - MTL"
                    elif any(k in lower_name for k in ["driver"]):
                        resolved_expense = "401020 - COGS Logistics : Driver Service Expenses - MTL"
                    elif any(k in lower_name for k in ["biker", "fuel"]):
                        resolved_expense = "401010 - COGS Logistics : Biker Service Expense - MTL"

                # ✅ Dynamic Item Group
                qb_item_group = qb_item.get("SubItem") or "All Item Groups"
                if not frappe.db.exists("Item Group", qb_item_group):
                    ig = frappe.get_doc({
                        "doctype": "Item Group",
                        "item_group_name": qb_item_group,
                        "parent_item_group": "All Item Groups",
                        "is_group": 0
                    })
                    ig.insert(ignore_permissions=True)
                    frappe.db.commit()

                # ✅ Dynamic UOM
                stock_uom = qb_item.get("Unit") or "Nos"
                if not frappe.db.exists("UOM", stock_uom):
                    uom_doc = frappe.get_doc({"doctype": "UOM", "uom_name": stock_uom})
                    uom_doc.insert(ignore_permissions=True)
                    frappe.db.commit()

                # Check if item already exists by QuickBooks ID
                existing_item = frappe.db.exists("Item", {"custom_quickbooks_item_id": qb_item_id})
                if existing_item:
                    erp_item = frappe.get_doc("Item", existing_item)
                    erp_item.item_name = item_name
                    erp_item.description = description
                    erp_item.item_group = qb_item_group
                    erp_item.stock_uom = stock_uom
                    erp_item.is_stock_item = 1 if is_stock_item else 0
                    
                    # Update item_defaults
                    matched = False
                    for d in (erp_item.item_defaults or []):
                        if d.company == company:
                            d.income_account = resolved_income
                            d.expense_account = resolved_expense
                            matched = True
                            break
                    if not matched:
                        erp_item.append("item_defaults", {
                            "company": company,
                            "income_account": resolved_income,
                            "expense_account": resolved_expense
                        })

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
                    "custom_quickbooks_item_id": qb_item_id,
                    "item_defaults": [{
                        "company": company,
                        "income_account": resolved_income,
                        "expense_account": resolved_expense
                    }]
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
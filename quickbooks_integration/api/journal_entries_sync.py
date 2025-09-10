import frappe
import requests
import json
from frappe.utils import nowdate

@frappe.whitelist()
def sync_quickbooks_journal_entries():
    try:
        # ✅ Load QuickBooks Settings
        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        # ✅ Use production/sandbox base URL
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"

        url = f"{base_url}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        query = "SELECT * FROM JournalEntry MAXRESULTS 10"
        response = requests.post(url, headers=headers, data=query)

        if response.status_code == 401:
            frappe.throw("Unauthorized: Token expired or invalid. Please reconnect QuickBooks.")
        elif response.status_code == 403:
            frappe.throw("Forbidden: Access denied by QuickBooks. Check your app permissions.")
        elif response.status_code != 200:
            frappe.throw(f"QuickBooks API Error: {response.status_code}, {response.text}")

        data = response.json()
        journal_entries = data.get("QueryResponse", {}).get("JournalEntry", [])
        print("🔎 Raw Journal Entry Response:")
        print(json.dumps(journal_entries, indent=4))

        if not journal_entries:
            return "No Journal Entries found in QuickBooks."

        # ✅ Get ERPNext default company
        company = frappe.defaults.get_user_default("Company")

        created_entries = []
        for je in journal_entries:
            qbo_je_id = je.get("Id")

            # Skip if already synced
            if frappe.db.exists("Journal Entry", {"custom_quickbooks_je_id": qbo_je_id}):
                continue

            # Create Journal Entry
            journal_entry = frappe.new_doc("Journal Entry")
            journal_entry.posting_date = je.get("TxnDate") or nowdate()
            journal_entry.company = company
            journal_entry.custom_quickbooks_je_id = qbo_je_id
            journal_entry.voucher_type = "Journal Entry"

            # ✅ Hardcode User Remark to avoid missing value error
            journal_entry.user_remark = f"QBO Journal Entry {qbo_je_id}"

            # ✅ Loop through line items
            for line in je.get("Line", []):
                if "JournalEntryLineDetail" not in line:
                    continue

                detail = line["JournalEntryLineDetail"]
                qbo_acc_name = detail["AccountRef"]["name"]  # QBO Account Name

                # ✅ Fetch ERPNext Account using your custom mapping field
                erp_acc = frappe.db.get_value(
                    "Account",
                    {"custom_qbc_child_account_name": qbo_acc_name, "company": company},
                    "name"
                )

                if not erp_acc:
                    frappe.throw(f"⚠️ No ERPNext Account mapped for QuickBooks Account: {qbo_acc_name}")

                # ✅ Debit / Credit logic
                debit = credit = 0
                if detail.get("PostingType") == "Debit":
                    debit = line.get("Amount", 0)
                elif detail.get("PostingType") == "Credit":
                    credit = line.get("Amount", 0)

                journal_entry.append("accounts", {
                    "account": erp_acc,
                    "debit_in_account_currency": debit,
                    "credit_in_account_currency": credit
                })

            # ✅ Save and submit JE
            journal_entry.save(ignore_permissions=True)
            created_entries.append(journal_entry.name)
            print(f"✅ Created Journal Entry: {journal_entry.name} for QBO JE ID: {qbo_je_id}") 
            print(f"    Link: {frappe.utils.get_url_to_form('Journal Entry', journal_entry.name)}")
            print(f"    Accounts: {[d.account for d in journal_entry.accounts]}")
            print(f"    Total Debit: {sum(d.debit_in_account_currency for d in journal_entry.accounts)}")
            print(f"    Total Credit: {sum(d.credit_in_account_currency for d in journal_entry.accounts)}")
            print("--------------------------------------------------")

        return f"✅ Synced Journal Entries: {', '.join(created_entries)}"

    except Exception as e:
        frappe.log_error(message=str(e), title="QuickBooks JE Sync Error")
        return f"❌ Error occurred: {e}"

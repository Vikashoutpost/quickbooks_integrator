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
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw("No default company set in Global Defaults.")

        print(f"\n📊 Syncing {len(journal_entries)} journal entries from QuickBooks to {company}")

        created_entries = []
        skipped_entries = []
        failed_entries = []

        for je in journal_entries:
            qbo_je_id = je.get("Id")

            # Skip if already synced (using reference_no since custom field might not exist)
            existing_je = frappe.db.exists("Journal Entry", {"user_remark": f"QB-JE-{qbo_je_id}"})
            if existing_je:
                print(f"⏭️  Skipping JE {qbo_je_id} - already synced")
                skipped_entries.append(qbo_je_id)
                continue

            try:
                print(f"\n➡️  Processing JE {qbo_je_id} (Doc: {je.get('DocNumber', 'N/A')})")

                # Track if any accounts are missing
                missing_accounts = []
                has_depreciation_account = False
                account_lines = []  # Collect account lines first

                # ✅ First pass: Check all accounts and detect depreciation
                for line in je.get("Line", []):
                    if "JournalEntryLineDetail" not in line:
                        continue

                    detail = line["JournalEntryLineDetail"]
                    qbo_acc_id = detail["AccountRef"]["value"]  # QBO Account ID
                    qbo_acc_name = detail["AccountRef"]["name"]  # QBO Account Name
                    amount = line.get("Amount", 0)
                    posting_type = detail.get("PostingType", "")

                    print(f"   • QB Account: {qbo_acc_name} (ID: {qbo_acc_id}) | {posting_type}: {amount}")

                    # ✅ Try multiple methods to find the account
                    # Method 1: By account_number (QB{id})
                    erp_acc = frappe.db.get_value(
                        "Account",
                        {"account_number": f"QB{qbo_acc_id}", "company": company},
                        "name"
                    )

                    # Method 2: By account name (fallback)
                    if not erp_acc:
                        erp_acc = frappe.db.get_value(
                            "Account",
                            {"account_name": qbo_acc_name, "company": company, "is_group": 0},
                            "name"
                        )

                    if not erp_acc:
                        print(f"     ❌ Account not found in ERPNext")
                        missing_accounts.append(f"{qbo_acc_name} (QB ID: {qbo_acc_id})")
                        continue
                    else:
                        print(f"     ✓ Mapped to: {erp_acc}")

                    # Check if this is a depreciation account
                    account_details = frappe.db.get_value("Account", erp_acc,
                        ["account_type", "account_name"], as_dict=True)

                    # Check multiple conditions for depreciation
                    if account_details:
                        account_type = account_details.account_type
                        account_name_lower = account_details.account_name.lower()

                        # Detect depreciation by account type or name
                        if (account_type in ["Depreciation", "Accumulated Depreciation"] or
                            "depreciation" in account_name_lower or
                            "accumulated" in account_name_lower):
                            has_depreciation_account = True
                            print(f"   🔍 Detected depreciation account: {account_details.account_name} (Type: {account_type})")

                    # ✅ Debit / Credit logic
                    debit = credit = 0
                    if detail.get("PostingType") == "Debit":
                        debit = line.get("Amount", 0)
                    elif detail.get("PostingType") == "Credit":
                        credit = line.get("Amount", 0)

                    # Store account line for later
                    account_lines.append({
                        "account": erp_acc,
                        "debit_in_account_currency": debit,
                        "credit_in_account_currency": credit
                    })

                # Check if any accounts are missing
                if missing_accounts:
                    print(f"⏭️  Skipping JE {qbo_je_id} - Missing accounts: {', '.join(missing_accounts)}")
                    failed_entries.append(f"{qbo_je_id} (missing accounts)")
                    continue

                # Check if we have any accounts
                if not account_lines:
                    print(f"⏭️  Skipping JE {qbo_je_id} - No accounts found")
                    failed_entries.append(f"{qbo_je_id} (no accounts)")
                    continue

                # ✅ Now create the journal entry with correct entry_type BEFORE adding accounts
                journal_entry = frappe.new_doc("Journal Entry")
                journal_entry.posting_date = je.get("TxnDate") or nowdate()
                journal_entry.company = company
                journal_entry.voucher_type = "Journal Entry"
                journal_entry.user_remark = f"QB-JE-{qbo_je_id}: {je.get('DocNumber', '')}"

                # Set entry_type to "Depreciation Entry" if depreciation accounts are involved
                if has_depreciation_account:
                    journal_entry.entry_type = "Depreciation Entry"
                    print(f"   ✓ Set entry_type to 'Depreciation Entry'")

                # Now add all the account lines
                for acc_line in account_lines:
                    journal_entry.append("accounts", acc_line)

                # ✅ Save JE (don't submit - leave as draft for review)
                journal_entry.flags.ignore_mandatory = True
                journal_entry.flags.ignore_validate = True  # Bypass validation
                journal_entry.save(ignore_permissions=True)
                created_entries.append(journal_entry.name)

                entry_type_str = f" [Type: {journal_entry.entry_type}]" if has_depreciation_account else ""
                print(f"✅ Created Journal Entry: {journal_entry.name} for QB JE ID: {qbo_je_id}{entry_type_str}")
                print(f"   Accounts: {len(journal_entry.accounts)} | Total Debit: {sum(d.debit_in_account_currency for d in journal_entry.accounts)} | Total Credit: {sum(d.credit_in_account_currency for d in journal_entry.accounts)}")

            except Exception as je_err:
                print(f"❌ Failed to create JE {qbo_je_id}: {str(je_err)}")
                frappe.log_error(frappe.get_traceback(), f"JE Sync Failed: {qbo_je_id}")
                failed_entries.append(f"{qbo_je_id} (error)")

        summary = f"\n✅ JE Sync Complete! Created: {len(created_entries)}, Skipped: {len(skipped_entries)}, Failed: {len(failed_entries)}, Total: {len(journal_entries)}"
        print(summary)
        return summary

    except Exception as e:
        frappe.log_error(message=str(e), title="QuickBooks JE Sync Error")
        return f"❌ Error occurred: {e}"

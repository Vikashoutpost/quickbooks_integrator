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

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        # Fetch all payments with pagination (QB API returns max 1000 records per request)
        all_payments = []
        start_position = 1
        max_results = 1000

        print(f"📡 Fetching payments from QuickBooks...")

        while True:
            query = f"SELECT * FROM Payment STARTPOSITION {start_position} MAXRESULTS {max_results}"
            print(f"   Query: {query}")

            response = requests.post(endpoint, headers=headers, data=query)

            if response.status_code != 200:
                print(f"❌ Failed to fetch payments: {response.text}")
                return f"Failed to fetch payments: {response.text}"

            payment_data = response.json()
            payments_batch = payment_data.get("QueryResponse", {}).get("Payment", [])

            if not payments_batch:
                break

            all_payments.extend(payments_batch)
            print(f"   Fetched {len(payments_batch)} payments (Total so far: {len(all_payments)})")

            # If we got less than max_results, we've reached the end
            if len(payments_batch) < max_results:
                break

            start_position += max_results

        payments = all_payments
        print(f"\n📊 Total Payments Fetched: {len(payments)}")

        if not payments:
            return "No payments found in QuickBooks."

        synced_count = 0
        skipped_count = 0

        # Get default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw("No default company set in Global Defaults.")

        company_currency = frappe.get_cached_value("Company", company, "default_currency")

        # Cache for QuickBooks account details to avoid repeated API calls
        qb_account_cache = {}

        for qb_payment in payments:
            try:
                qb_payment_id = qb_payment.get("Id")
                amount = qb_payment.get("TotalAmt", 0)
                txn_date = qb_payment.get("TxnDate", nowdate())
                customer_ref = qb_payment.get("CustomerRef", {}).get("value")
                customer_name = qb_payment.get("CustomerRef", {}).get("name", "Unknown Customer")

                # Get payment description/memo
                payment_memo = qb_payment.get("PrivateNote", "") or qb_payment.get("CustomerMemo", {}).get("value", "")

                # Get deposit account (bank account in QuickBooks)
                deposit_account_ref = qb_payment.get("DepositToAccountRef", {})
                qb_bank_account_id = deposit_account_ref.get("value", "")
                qb_bank_account_name = deposit_account_ref.get("name", "")

                # If bank account name is not provided, fetch it from QuickBooks using the account ID
                if qb_bank_account_id and not qb_bank_account_name:
                    # Check cache first
                    if qb_bank_account_id in qb_account_cache:
                        qb_bank_account_name = qb_account_cache[qb_bank_account_id]
                        print(f"   Using cached QB Account Name: {qb_bank_account_name} for ID: {qb_bank_account_id}")
                    else:
                        try:
                            account_endpoint = f"{base_url}/v3/company/{realm_id}/account/{qb_bank_account_id}"
                            account_response = requests.get(account_endpoint, headers=headers)
                            if account_response.status_code == 200:
                                account_data = account_response.json()
                                qb_bank_account_name = account_data.get("Account", {}).get("Name", "Not specified")
                                # Cache the result
                                qb_account_cache[qb_bank_account_id] = qb_bank_account_name
                                print(f"   Fetched QB Account Name: {qb_bank_account_name} for ID: {qb_bank_account_id}")
                            else:
                                qb_bank_account_name = "Not specified"
                                print(f"   ⚠️  Failed to fetch QB account details for ID {qb_bank_account_id}: {account_response.status_code}")
                        except Exception as acc_err:
                            qb_bank_account_name = "Not specified"
                            print(f"   ⚠️  Error fetching QB account: {acc_err}")

                if not qb_bank_account_name:
                    qb_bank_account_name = "Not specified"

                # Get currency from payment (defaults to company currency if not specified)
                payment_currency_ref = qb_payment.get("CurrencyRef", {})
                payment_currency = payment_currency_ref.get("value", company_currency) if payment_currency_ref else company_currency

                print(f"\n➡️ Processing Payment: {qb_payment_id}, Date: {txn_date}, Amount: {amount}, Currency: {payment_currency}")
                print(f"   Customer: {customer_name} (QB ID: {customer_ref})")
                print(f"   QB Bank Account: {qb_bank_account_name} (ID: {qb_bank_account_id})")
                print(f"   Description: {payment_memo if payment_memo else 'No description'}")

                # Skip invalid/zero payments
                if not amount or float(amount) <= 0:
                    print(f"⚠️  Skipping payment {qb_payment_id} - amount is {amount}")
                    skipped_count += 1
                    continue

                # ✅ Find ERPNext customer using QuickBooks Customer Id
                erp_customer = frappe.db.get_value(
                    "Customer",
                    {"custom_quickbooks_customer_id": customer_ref},
                    "name"
                )

                if not erp_customer:
                    print(f"⏭️  Skipping payment {qb_payment_id} - Customer QB ID {customer_ref} ({customer_name}) not found in ERPNext")
                    skipped_count += 1
                    continue

                print(f"✅ Found ERPNext Customer: {erp_customer} for QuickBooks ID {customer_ref}")

                # ✅ Get Trade Receivables account (NOT QB Accounts Receivable)
                # Based on COA: Trade Receivables - NGN (121010) or Trade Receivables - USD (121020)
                # Look for accounts with "Trade Receivable" in the name and matching currency
                receivable_account = frappe.db.sql("""
                    SELECT name
                    FROM `tabAccount`
                    WHERE account_type = 'Receivable'
                    AND company = %(company)s
                    AND account_currency = %(currency)s
                    AND is_group = 0
                    AND disabled = 0
                    AND (account_name LIKE '%%Trade Receivable%%' OR account_number LIKE '121%%')
                    ORDER BY
                        CASE WHEN account_name LIKE '%%Trade Receivable%%' THEN 1 ELSE 2 END,
                        creation
                    LIMIT 1
                """, {"company": company, "currency": payment_currency}, as_dict=True)

                if receivable_account:
                    receivable_account = receivable_account[0].name
                else:
                    # Fallback to default receivable account
                    receivable_account = frappe.get_cached_value("Company", company, "default_receivable_account")
                    if not receivable_account:
                        print(f"⏭️  Skipping payment {qb_payment_id} - No receivable account found for currency {payment_currency}")
                        skipped_count += 1
                        continue
                    print(f"⚠️  Using default receivable account {receivable_account} (Trade Receivables not found)")

                # ✅ Get currency-specific bank account from Bank Account doctype
                # Based on COA: FCMB, Globus accounts for NGN; Globus USD accounts for USD
                # Strategy:
                # 1. First try to match by QuickBooks Account ID (e.g., QB140)
                # 2. Then try to match by QuickBooks bank account name
                # 3. Finally, fallback to first available account with matching currency

                bank_gl_account = None
                party_bank_account = None
                match_method = ""

                # Get all Bank Accounts for this company
                all_bank_accounts = frappe.get_all("Bank Account",
                    filters={"company": company, "disabled": 0},
                    fields=["name", "account", "bank", "bank_account_no", "account_name"])

                # Strategy 1: Try to match by QB Account ID (account_number = QB{qb_bank_account_id})
                if qb_bank_account_id:
                    qb_account_number = f"QB{qb_bank_account_id}"
                    for ba in all_bank_accounts:
                        if ba.account:
                            acc_number = frappe.db.get_value("Account", ba.account, "account_number")
                            if acc_number == qb_account_number:
                                account_currency = frappe.db.get_value("Account", ba.account, "account_currency")
                                if account_currency == payment_currency:
                                    bank_gl_account = ba.account
                                    party_bank_account = ba.name
                                    match_method = f"QB Account ID ({qb_account_number})"
                                    break

                # Strategy 2: Try to match by bank account name (e.g., "FCMB Bank" in QB matches "FCMB" in ERP)
                if not bank_gl_account and qb_bank_account_name and qb_bank_account_name != "Not specified":
                    # Extract key words from QB bank name (e.g., "FCMB", "Globus", "Lenco")
                    # Filter out generic words like "Bank", "Limited", etc.
                    generic_words = {"BANK", "LIMITED", "LTD", "INC", "PLC", "LLC", "ACCOUNT"}
                    qb_bank_keywords = [word.upper() for word in qb_bank_account_name.split()
                                       if word.upper() not in generic_words and len(word) >= 4]

                    # If no specific keywords found, use all words
                    if not qb_bank_keywords:
                        qb_bank_keywords = [word.upper() for word in qb_bank_account_name.split() if len(word) >= 4]

                    # Try to match with specific keywords first
                    for ba in all_bank_accounts:
                        if ba.account:
                            # Get both the Account name and Bank Account name for matching
                            erp_account_name = frappe.db.get_value("Account", ba.account, "account_name") or ""
                            erp_bank_account_name = ba.name or ""
                            erp_bank_name = ba.bank or ""

                            # Combine all possible names for matching
                            search_text = f"{erp_account_name} {erp_bank_account_name} {erp_bank_name}".upper()

                            # Check for keyword match (prioritize specific keywords)
                            for keyword in qb_bank_keywords:
                                if keyword in search_text:
                                    account_currency = frappe.db.get_value("Account", ba.account, "account_currency")
                                    if account_currency == payment_currency:
                                        bank_gl_account = ba.account
                                        party_bank_account = ba.name
                                        match_method = f"Bank Name Match ({keyword})"
                                        break

                            if bank_gl_account:
                                break

                # Strategy 3: Fallback to first account with matching currency
                if not bank_gl_account:
                    for ba in all_bank_accounts:
                        if ba.account:
                            account_currency = frappe.db.get_value("Account", ba.account, "account_currency")
                            if account_currency == payment_currency:
                                bank_gl_account = ba.account
                                party_bank_account = ba.name
                                match_method = f"Currency Fallback ({payment_currency})"
                                break

                if not bank_gl_account:
                    print(f"⏭️  Skipping payment {qb_payment_id} - No bank account found for currency {payment_currency}")
                    skipped_count += 1
                    continue

                print(f"✅ Using Accounts - Receivable: {receivable_account}, Bank GL: {bank_gl_account}, Bank Account: {party_bank_account}")
                print(f"   Match Method: {match_method}, Currency: {payment_currency}")

                # ✅ Check if already synced (using reference_no since custom field might not exist)
                existing_pe = frappe.db.exists("Payment Entry", {"reference_no": f"QB-{qb_payment_id}"})
                if existing_pe:
                    print(f"⏭️  Payment {qb_payment_id} already synced. Skipping.")
                    skipped_count += 1
                    continue

                # ✅ Create new Payment Entry
                pe = frappe.new_doc("Payment Entry")
                pe.payment_type = "Receive"
                pe.company = company
                pe.party_type = "Customer"
                pe.party = erp_customer
                pe.posting_date = txn_date
                pe.paid_amount = amount
                pe.received_amount = amount
                pe.reference_no = f"QB-{qb_payment_id}"
                pe.reference_date = txn_date

                # Accounts with currency-specific mapping
                pe.paid_from = receivable_account
                pe.paid_to = bank_gl_account
                pe.paid_from_account_currency = payment_currency
                pe.paid_to_account_currency = payment_currency

                # Set the Company Bank Account (this is the field that appears in the UI)
                if party_bank_account:
                    pe.bank_account = party_bank_account

                # Exchange rates (set to 1 for same currency transactions)
                pe.source_exchange_rate = 1
                pe.target_exchange_rate = 1

                pe.flags.ignore_mandatory = True  # Skip mandatory field validation
                pe.save(ignore_permissions=True)
                # Don't submit - leave as draft for user review

                print(f"✅ Created Payment Entry: {pe.name} for QB Payment {qb_payment_id}")
                print(f"   Amount: {amount} {payment_currency}, Customer: {erp_customer}")
                print(f"   Paid From: {receivable_account} → Paid To: {bank_gl_account}")
                print(f"   Company Bank Account: {party_bank_account if party_bank_account else 'Not set'}")
                print(f"   QB Bank: {qb_bank_account_name} (ID: {qb_bank_account_id})")
                synced_count += 1

            except Exception as pe_err:
                frappe.log_error(frappe.get_traceback(), f"Payment Sync Failed: {qb_payment.get('Id')}")
                print(f"❌ Error syncing payment {qb_payment.get('Id')}: {pe_err}")
                skipped_count += 1

        summary = f"✅ Payment Sync Complete! Created: {synced_count}, Skipped: {skipped_count}, Total: {len(payments)}"
        print(f"\n{summary}")
        return summary

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Payment Sync Error")
        return f"🔥 Error occurred: {str(e)}"

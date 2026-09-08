import frappe
import requests
from intuitlib.client import AuthClient
from frappe.utils import nowdate, getdate, flt

BANK_MAP = {
    # Exact QBO Account IDs
    "140": "119010 - FCMB Bank - MTL",
    "29": "119020 - Globus Bank - MTL",
    "1150040004": "119030 - Lenco Funding Account - MTL",
    "88": "119040 - Petty Cash - MTL",
    "1150040010": "119040 - Petty Cash - MTL",
    "1150040002": "119050 - Globus Bank USD - 5000032967 - MTL",
    "1150040000": "119060 - Globus Bank USD - 8000006697 - MTL",
    "172": "119070 - Movam Inc - MTL",

    # Keyword / Name matches
    "fcmb": "119010 - FCMB Bank - MTL",
    "globus bank - 8000006697": "119060 - Globus Bank USD - 8000006697 - MTL",
    "globus bank - 5000032967": "119050 - Globus Bank USD - 5000032967 - MTL",
    "5000032967": "119050 - Globus Bank USD - 5000032967 - MTL",
    "8000006697": "119060 - Globus Bank USD - 8000006697 - MTL",
    "globus": "119020 - Globus Bank - MTL",
    "lenco": "119030 - Lenco Funding Account - MTL",
    "petty cash": "119040 - Petty Cash - MTL",
    "cash in hand": "119040 - Petty Cash - MTL",
    "cash": "119040 - Petty Cash - MTL",
    "movam inc": "119070 - Movam Inc - MTL",
    "fcmb usd": "119080 - FCMB USD - MTL",
    "omnipay": "119090 - Omnipay/Movam Technologies - MTL",
}


def refresh_qb_token(settings):
    """Refreshes the OAuth access token and updates the Quickbook Settings doctype."""
    try:
        auth_client = AuthClient(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            environment=settings.environment or "sandbox",
            redirect_uri=settings.redirect_uri
        )
        auth_client.refresh(refresh_token=settings.refresh_token)
        frappe.db.set_value("Quickbook Settings", "Quickbook Settings", {
            "access_token": auth_client.access_token,
            "refresh_token": auth_client.refresh_token
        })
        frappe.db.commit()
        return auth_client.access_token
    except Exception as e:
        frappe.log_error(f"Failed to refresh QuickBooks token: {str(e)}", "QuickBooks Token Refresh Error")
        return None


def resolve_bank_account(bank_ref, currency="NGN", company="Movam Technologies Limited"):
    """Resolve QuickBooks Bank Account to official Movam ERPNext Account"""
    if not bank_ref:
        return "119020 - Globus Bank - MTL" if currency == "NGN" else "119050 - Globus Bank USD - 5000032967 - MTL"

    b_name = (bank_ref.get("name") or "").strip().lower()
    b_val = str(bank_ref.get("value") or "").strip()

    # 1. Match from explicit ID map
    if b_val and b_val in BANK_MAP:
        return BANK_MAP[b_val]

    # 2. Match from explicit keyword map
    for k, acc in BANK_MAP.items():
        if (b_name and k in b_name) or k == b_val:
            if frappe.db.exists("Account", acc):
                return acc

    # 3. Match exact account name
    if b_name:
        cand = frappe.db.sql("""
            SELECT name FROM `tabAccount` 
            WHERE company = %s AND is_group = 0 AND disabled = 0 
              AND name NOT LIKE 'QB-%%' 
              AND (LOWER(account_name) = %s OR LOWER(name) LIKE %s)
            LIMIT 1
        """, (company, b_name, f"%{b_name}%"))

        if cand and cand[0][0]:
            return cand[0][0]

    return "119020 - Globus Bank - MTL" if currency == "NGN" else "119050 - Globus Bank USD - 5000032967 - MTL"


def fetch_payment_attachments(qb_id, je_name, headers, base_url, realm_id, attachables=None):
    """Fetch and attach files from QuickBooks Attachable for Payment/BillPayment"""
    try:
        if attachables is None:
            endpoint = f"{base_url}/v3/company/{realm_id}/query"
            query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{qb_id}'"
            res = requests.post(endpoint, headers=headers, data=query, timeout=30)
            if res.status_code != 200:
                return 0
            attachables = res.json().get("QueryResponse", {}).get("Attachable", [])

        if not attachables:
            return 0

        attached_count = 0

        for att in attachables:
            file_name = att.get("FileName") or f"QB_Payment_Attachment_{att.get('Id')}.bin"
            att_id = att.get("Id")

            if frappe.db.exists("File", {"attached_to_doctype": "Journal Entry", "attached_to_name": je_name, "file_name": file_name}):
                continue

            temp_uri = att.get("TempDownloadUri")
            file_content = None

            if temp_uri:
                try:
                    r = requests.get(temp_uri, timeout=30)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            if not file_content:
                try:
                    dl_url = f"{base_url}/v3/company/{realm_id}/download/{att_id}"
                    r = requests.get(dl_url, headers={"Authorization": headers.get("Authorization")}, timeout=30)
                    if r.status_code == 200:
                        file_content = r.content
                except Exception:
                    file_content = None

            if file_content:
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "attached_to_doctype": "Journal Entry",
                    "attached_to_name": je_name,
                    "content": file_content,
                    "is_private": 1
                })
                file_doc.insert(ignore_permissions=True)
                attached_count += 1

        return attached_count
    except Exception as e:
        frappe.log_error(f"Error fetching attachments for payment {qb_id}: {str(e)}", "QB Payment Attachment Sync")
        return 0


@frappe.whitelist()
def enqueue_sync_payments():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.payments_sync.sync_quickbooks_payments",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "Payments sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def sync_quickbooks_payments(user=None):
    """Sync both Customer Payments and Vendor Bill Payments as Journal Entries"""
    try:
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"

        if not access_token or not realm_id:
            frappe.throw("Access Token or Realm ID missing. Please connect to QuickBooks.")

        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/text"
        }

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"

        created_count = 0
        updated_count = 0
        total_attachments = 0
        skipped = []

        # Pre-fetch existing submitted payments to skip them in O(1) memory lookup
        existing_payments = set(frappe.db.sql_list("SELECT custom_quickbooks_je_id FROM `tabJournal Entry` WHERE docstatus = 1 AND custom_quickbooks_je_id IS NOT NULL"))

        # Pre-load attachables map in bulk (eliminates thousands of slow individual queries)
        attachable_map = {}
        try:
            start_att = 1
            for _ in range(10):
                q = f"SELECT * FROM Attachable STARTPOSITION {start_att} MAXRESULTS 1000"
                r = requests.post(endpoint, headers=headers, data=q, timeout=30)
                if r.status_code == 200:
                    atts = r.json().get("QueryResponse", {}).get("Attachable", [])
                    for a in atts:
                        for ref in a.get("AttachableRef", []):
                            val = ref.get("EntityRef", {}).get("value")
                            if val:
                                attachable_map.setdefault(str(val), []).append(a)
                    if len(atts) < 1000:
                        break
                    start_att += 1000
                else:
                    break
        except Exception as e:
            frappe.log_error(f"Attachable pre-fetch warning: {str(e)}", "Attachable Bulk Fetch")

        # =========================================================================
        # 1. FETCH & SYNC CUSTOMER PAYMENTS (`Payment`)
        # =========================================================================
        all_payments = []
        start_position = 1
        max_results = 500

        while True:
            query = f"SELECT * FROM Payment STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Payment Sync API Error")
                break

            data = response.json()
            batch = data.get("QueryResponse", {}).get("Payment", [])
            if not batch:
                break

            all_payments.extend(batch)
            if len(batch) < max_results:
                break
            start_position += max_results

        total_pay = len(all_payments)

        for idx, p in enumerate(all_payments, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Payments sync stopped by user. Processed {created_count + updated_count} entries."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 25 == 0 or idx == total_pay:
                try:
                    frappe.publish_progress(
                        percent=round((idx / max(total_pay, 1)) * 50),
                        title="Syncing Customer Payments",
                        description=f"Processing payment {idx} of {total_pay}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = p.get("Id")
                custom_je_id = f"PAY-{qb_id}"
                if custom_je_id in existing_payments:
                    continue

                doc_number = p.get("DocNumber")
                total_amt = flt(p.get("TotalAmt", 0))
                if total_amt <= 0:
                    continue

                txn_date = p.get("TxnDate") or nowdate()
                currency = (p.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(p.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Customer mapping
                cust_ref = p.get("CustomerRef", {}) or {}
                cust_id = cust_ref.get("value")
                cust_name = cust_ref.get("name") or f"QuickBooks Customer {cust_id}"

                customer = None
                if cust_id:
                    customer = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": cust_id}, "name")
                if not customer:
                    customer = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name")
                if not customer and cust_name:
                    customer = frappe.db.get_value("Customer", {"customer_name": ["like", f"%{cust_name.strip()}%"]}, "name")
                if not customer:
                    try:
                        cdoc = frappe.get_doc({
                            "doctype": "Customer",
                            "customer_name": cust_name,
                            "custom_quickbooks_customer_id": cust_id,
                            "customer_group": "All Customer Groups",
                            "territory": "All Territories",
                            "default_currency": currency,
                        })
                        cdoc.flags.ignore_mandatory = True
                        cdoc.insert(ignore_permissions=True)
                        customer = cdoc.name
                    except Exception:
                        customer = cust_name

                # Bank Account (Debit) & Receivable Account (Credit)
                bank_ref = p.get("DepositToAccountRef", {}) or {}
                bank_account = resolve_bank_account(bank_ref, currency, company)
                cust_curr = frappe.db.get_value("Customer", customer, "default_currency") or currency
                receivable_account = "121020 - Trade Receivables - USD - MTL" if (cust_curr == "USD" or currency == "USD") else "121010 - Trade Receivables - NGN - MTL"

                custom_je_id = f"PAY-{qb_id}"
                ref_no = f"PAY-{doc_number}" if doc_number else f"PAY-{qb_id}"

                # Handle multi-currency amount conversion
                bank_curr = frappe.db.get_value("Account", bank_account, "account_currency") or "NGN"
                ar_curr = frappe.db.get_value("Account", receivable_account, "account_currency") or "NGN"

                bank_amt = total_amt
                bank_rate = exchange_rate
                if bank_curr == "NGN" and currency == "USD":
                    bank_amt = round(total_amt * exchange_rate, 2)
                    bank_rate = 1.0

                ar_amt = total_amt
                ar_rate = exchange_rate
                if ar_curr == "NGN" and currency == "USD":
                    ar_amt = round(total_amt * exchange_rate, 2)
                    ar_rate = 1.0

                accounts = [
                    {
                        "account": bank_account,
                        "debit_in_account_currency": round(flt(bank_amt), 2),
                        "credit_in_account_currency": 0,
                        "exchange_rate": bank_rate,
                        "cost_center": "QuickBooks Payment - MTL",
                        "channel": "QuickBooks",
                        "department": "QuickBooks - MTL",
                        "user_remark": f"Customer Payment QBO - {doc_number or qb_id}",
                    },
                    {
                        "account": receivable_account,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": round(flt(ar_amt), 2),
                        "exchange_rate": ar_rate,
                        "cost_center": "QuickBooks Payment - MTL",
                        "channel": "QuickBooks",
                        "department": "QuickBooks - MTL",
                        "party_type": "Customer",
                        "party": customer,
                        "user_remark": f"Customer Payment QBO - {doc_number or qb_id}",
                    }
                ]

                # Pre-round and auto-balance
                for a in accounts:
                    a["debit_in_account_currency"] = flt(a.get("debit_in_account_currency", 0), 2)
                    a["credit_in_account_currency"] = flt(a.get("credit_in_account_currency", 0), 2)

                existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_je_id}, "name")
                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    if je.docstatus == 0:
                        je.accounts = []
                        for acc in accounts:
                            je.append("accounts", acc)
                        je.posting_date = getdate(txn_date)
                        je.cheque_no = ref_no
                        je.cheque_date = getdate(txn_date)
                        je.multi_currency = 1
                        je.flags.ignore_permissions = True
                        je.flags.ignore_mandatory = True
                        je.flags.ignore_links = True
                        je.save(ignore_permissions=True)
                        je.flags.ignore_permissions = True
                        je.submit()
                        updated_count += 1
                        je_name = je.name
                    else:
                        je_name = existing_je
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": "Bank Entry",
                        "company": company,
                        "posting_date": getdate(txn_date),
                        "cheque_no": ref_no,
                        "cheque_date": getdate(txn_date),
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": custom_je_id,
                        "user_remark": f"Customer Payment QBO - {doc_number or qb_id}",
                        "party_type": "Customer",
                        "party": customer,
                        "_user_tags": ",QB Payments,"
                    })
                    je.flags.ignore_permissions = True
                    je.flags.ignore_mandatory = True
                    je.flags.ignore_links = True
                    je.insert(ignore_permissions=True)
                    je.flags.ignore_permissions = True
                    je.submit()
                    created_count += 1
                    je_name = je.name

                # Add Tag
                try:
                    frappe.db.set_value("Journal Entry", je_name, "_user_tags", ",QB Payments,")
                    if not frappe.db.exists("Tag", "QB Payments"):
                        frappe.get_doc({"doctype": "Tag", "name": "QB Payments"}).insert(ignore_permissions=True)
                    if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": "QB Payments"}):
                        frappe.get_doc({
                            "doctype": "Tag Link",
                            "document_type": "Journal Entry",
                            "document_name": je_name,
                            "tag": "QB Payments"
                        }).insert(ignore_permissions=True)
                except Exception:
                    pass

                # Attachments
                att_count = fetch_payment_attachments(qb_id, je_name, headers, base_url, realm_id, attachables=attachable_map.get(str(qb_id), []))
                total_attachments += att_count

                if (created_count + updated_count) % 50 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"Payment {p.get('DocNumber') or p.get('Id')} skipped: {str(inner_e)}")
                continue

        frappe.db.commit()

        # =========================================================================
        # 2. FETCH & SYNC VENDOR BILL PAYMENTS (`BillPayment`)
        # =========================================================================
        all_bill_payments = []
        start_position = 1

        while True:
            query = f"SELECT * FROM BillPayment STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks BillPayment Sync API Error")
                break

            data = response.json()
            batch = data.get("QueryResponse", {}).get("BillPayment", [])
            if not batch:
                break

            all_bill_payments.extend(batch)
            if len(batch) < max_results:
                break
            start_position += max_results

        total_bp = len(all_bill_payments)

        for idx, bp in enumerate(all_bill_payments, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Bill payments sync stopped by user. Processed {created_count + updated_count} entries."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 50 == 0 or idx == total_bp:
                try:
                    frappe.publish_progress(
                        percent=50 + round((idx / max(total_bp, 1)) * 50),
                        title="Syncing Vendor Bill Payments",
                        description=f"Processing bill payment {idx} of {total_bp}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = bp.get("Id")
                custom_je_id = f"BILLPAY-{qb_id}"
                if custom_je_id in existing_payments:
                    continue

                doc_number = bp.get("DocNumber")
                total_amt = flt(bp.get("TotalAmt", 0))
                if total_amt <= 0:
                    continue

                txn_date = bp.get("TxnDate") or nowdate()
                currency = (bp.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(bp.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Vendor mapping
                vendor_ref = bp.get("VendorRef", {}) or {}
                vendor_id = vendor_ref.get("value")
                vendor_name = vendor_ref.get("name") or f"QuickBooks Vendor {vendor_id}"

                supplier = None
                if vendor_id:
                    supplier = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": vendor_id}, "name")
                if not supplier:
                    supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name")
                if not supplier and vendor_name:
                    supplier = frappe.db.get_value("Supplier", {"supplier_name": ["like", f"%{vendor_name.strip()}%"]}, "name")
                if not supplier:
                    try:
                        sdoc = frappe.get_doc({
                            "doctype": "Supplier",
                            "supplier_name": vendor_name,
                            "custom_quickbooks_vendor_id": vendor_id,
                            "supplier_group": "All Supplier Groups",
                            "supplier_type": "Private Limited Company(Ltd)",
                            "default_currency": currency,
                        })
                        sdoc.flags.ignore_mandatory = True
                        sdoc.insert(ignore_permissions=True)
                        supplier = sdoc.name
                    except Exception:
                        supplier = vendor_name

                # Bank Account (Credit) & Payable Account (Debit)
                check_pay = bp.get("CheckPayment", {}) or {}
                cc_pay = bp.get("CreditCardPayment", {}) or {}
                bank_ref = check_pay.get("BankAccountRef") or cc_pay.get("CCAccountRef") or bp.get("BankAccountRef", {}) or {}
                bank_account = resolve_bank_account(bank_ref, currency, company)
                supp_curr = frappe.db.get_value("Supplier", supplier, "default_currency") or currency
                payable_account = "225020 - Trade Creditors - USD - MTL" if (supp_curr == "USD" or currency == "USD") else "225010 - Trade Creditors - NGN - MTL"

                custom_je_id = f"BILLPAY-{qb_id}"
                ref_no = f"BP-{doc_number}" if doc_number else f"BILLPAY-{qb_id}"

                # Handle multi-currency amount conversion
                bank_curr = frappe.db.get_value("Account", bank_account, "account_currency") or "NGN"
                ap_curr = frappe.db.get_value("Account", payable_account, "account_currency") or "NGN"

                ap_amt = total_amt
                ap_rate = exchange_rate
                if ap_curr == "NGN" and currency == "USD":
                    ap_amt = round(total_amt * exchange_rate, 2)
                    ap_rate = 1.0

                bank_amt = total_amt
                bank_rate = exchange_rate
                if bank_curr == "NGN" and currency == "USD":
                    bank_amt = round(total_amt * exchange_rate, 2)
                    bank_rate = 1.0

                accounts = [
                    {
                        "account": payable_account,
                        "debit_in_account_currency": round(flt(ap_amt), 2),
                        "credit_in_account_currency": 0,
                        "exchange_rate": ap_rate,
                        "cost_center": "QuickBooks Payment - MTL",
                        "channel": "QuickBooks",
                        "department": "QuickBooks - MTL",
                        "party_type": "Supplier",
                        "party": supplier,
                        "user_remark": f"Bill Payment QBO - {doc_number or qb_id}",
                    },
                    {
                        "account": bank_account,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": round(flt(bank_amt), 2),
                        "exchange_rate": bank_rate,
                        "cost_center": "QuickBooks Payment - MTL",
                        "channel": "QuickBooks",
                        "department": "QuickBooks - MTL",
                        "user_remark": f"Bill Payment QBO - {doc_number or qb_id}",
                    }
                ]

                # Pre-round and auto-balance
                for a in accounts:
                    a["debit_in_account_currency"] = flt(a.get("debit_in_account_currency", 0), 2)
                    a["credit_in_account_currency"] = flt(a.get("credit_in_account_currency", 0), 2)

                existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_je_id}, "name")
                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    if je.docstatus == 0:
                        je.accounts = []
                        for acc in accounts:
                            je.append("accounts", acc)
                        je.posting_date = getdate(txn_date)
                        je.cheque_no = ref_no
                        je.cheque_date = getdate(txn_date)
                        je.multi_currency = 1
                        je.flags.ignore_permissions = True
                        je.flags.ignore_mandatory = True
                        je.flags.ignore_links = True
                        je.save(ignore_permissions=True)
                        je.flags.ignore_permissions = True
                        je.submit()
                        updated_count += 1
                        je_name = je.name
                    else:
                        je_name = existing_je
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": "Bank Entry",
                        "company": company,
                        "posting_date": getdate(txn_date),
                        "cheque_no": ref_no,
                        "cheque_date": getdate(txn_date),
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": custom_je_id,
                        "user_remark": f"Bill Payment QBO - {doc_number or qb_id}",
                        "party_type": "Supplier",
                        "party": supplier,
                        "_user_tags": ",QB Payments,"
                    })
                    je.flags.ignore_permissions = True
                    je.flags.ignore_mandatory = True
                    je.flags.ignore_links = True
                    je.insert(ignore_permissions=True)
                    je.flags.ignore_permissions = True
                    je.submit()
                    created_count += 1
                    je_name = je.name

                # Add Tag
                try:
                    frappe.db.set_value("Journal Entry", je_name, "_user_tags", ",QB Payments,")
                    if not frappe.db.exists("Tag", "QB Payments"):
                        frappe.get_doc({"doctype": "Tag", "name": "QB Payments"}).insert(ignore_permissions=True)
                    if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": "QB Payments"}):
                        frappe.get_doc({
                            "doctype": "Tag Link",
                            "document_type": "Journal Entry",
                            "document_name": je_name,
                            "tag": "QB Payments"
                        }).insert(ignore_permissions=True)
                except Exception:
                    pass

                # Attachments
                att_count = fetch_payment_attachments(qb_id, je_name, headers, base_url, realm_id, attachables=attachable_map.get(str(qb_id), []))
                total_attachments += att_count

                if (created_count + updated_count) % 50 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"BillPayment {bp.get('DocNumber') or bp.get('Id')} skipped: {str(inner_e)}")
                continue

        frappe.db.commit()

        summary_msg = f"Payments Sync Completed: {created_count} created, {updated_count} updated, {total_attachments} files attached (Total processed: {created_count + updated_count})."
        if skipped:
            summary_msg += f" Skipped {len(skipped)} entries."
            frappe.log_error("\n".join(skipped), "QuickBooks Payment Sync Skipped")

        if user:
            frappe.publish_realtime("msgprint", summary_msg, user=user)

        return summary_msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Payment Sync Main Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

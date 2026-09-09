import frappe
import requests
from intuitlib.client import AuthClient
from frappe.utils import nowdate, getdate, flt
from quickbooks_integration.api.payments_sync import BANK_MAP, resolve_bank_account


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


def prefetch_all_attachments(headers, base_url, realm_id, entity_type=None):
    """
    Fetch all QuickBooks Attachable metadata in chunks of 1000 in memory.
    Reduces 8,000 separate HTTP queries (40+ mins) down to 1-2 batch queries (2 seconds)!
    Returns a dict: {(entity_type.lower(), entity_id): [attachable_dict, ...]}
    """
    attach_map = {}
    try:
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        start = 1
        max_results = 1000
        while True:
            query = f"SELECT * FROM Attachable STARTPOSITION {start} MAXRESULTS {max_results}"
            res = requests.post(endpoint, headers=headers, data=query, timeout=45)
            if res.status_code != 200:
                break
            batch = res.json().get("QueryResponse", {}).get("Attachable", [])
            if not batch:
                break
            for att in batch:
                for ref in att.get("AttachableRef", []) or []:
                    ent = ref.get("EntityRef", {}) or {}
                    e_type = (ent.get("type") or "").strip().lower()
                    e_id = str(ent.get("value") or "").strip()
                    if e_type and e_id:
                        key = (e_type, e_id)
                        if key not in attach_map:
                            attach_map[key] = []
                        attach_map[key].append(att)
            if len(batch) < max_results:
                break
            start += max_results
    except Exception as e:
        frappe.log_error(f"Error prefetching attachments: {str(e)}", "QB Attachable Batch Prefetch")
    return attach_map


def fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, prefix="QB_Attachment", preloaded_attachables=None, entity_type=None):
    """Fetch and attach files from QuickBooks Attachable using pre-fetched metadata if available"""
    try:
        if preloaded_attachables is not None:
            attachables = preloaded_attachables
        else:
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
            file_name = att.get("FileName") or f"{prefix}_{att.get('Id')}.bin"
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

            # If QuickBooks returned a download URL string instead of raw binary, fetch the actual file from that URL
            if file_content and (file_content.startswith(b"http://") or file_content.startswith(b"https://")):
                try:
                    actual_dl_url = file_content.decode("utf-8").strip()
                    r_actual = requests.get(actual_dl_url, timeout=30)
                    if r_actual.status_code == 200:
                        file_content = r_actual.content
                    else:
                        file_content = None
                except Exception:
                    file_content = None

            if file_content:
                if not hasattr(frappe.local, "rollback_observers"):
                    frappe.local.rollback_observers = []

                ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").upper()
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "file_type": ext,
                    "attached_to_doctype": "Journal Entry",
                    "attached_to_name": je_name,
                    "content": file_content,
                    "is_private": 1
                })
                file_doc.insert(ignore_permissions=True)
                attached_count += 1

        return attached_count
    except Exception as e:
        frappe.log_error(f"Error fetching attachments for {qb_id}: {str(e)}", "QB Attachment Sync")
        return 0


def tag_journal_entry(je_name, tag_name):
    """Add standardized tag to Journal Entry and Tag Link table"""
    try:
        frappe.db.set_value("Journal Entry", je_name, "_user_tags", f",{tag_name},")
        if not frappe.db.exists("Tag", tag_name):
            frappe.get_doc({"doctype": "Tag", "name": tag_name}).insert(ignore_permissions=True)
        if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": tag_name}):
            frappe.get_doc({
                "doctype": "Tag Link",
                "document_type": "Journal Entry",
                "document_name": je_name,
                "tag": tag_name
            }).insert(ignore_permissions=True)
    except Exception:
        pass


from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache


def resolve_account_from_ref(acc_ref, company, default_acc):
    """Resolve Account from QBO AccountRef using Centralized Account Mapper"""
    return resolve_account_master(acc_ref, company, default_acc=default_acc)


def get_or_create_customer(cust_ref, curr="NGN"):
    if not cust_ref:
        return frappe.db.get_value("Customer", {}, "name") or "QuickBooks Customer"
    cust_id = cust_ref.get("value")
    cust_name = cust_ref.get("name") or f"QuickBooks Customer {cust_id}"

    customer = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": cust_id}, "name") if cust_id else None
    if not customer and cust_name:
        customer = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name") or \
                   frappe.db.get_value("Customer", {"customer_name": ["like", f"%{cust_name}%"]}, "name") or \
                   frappe.db.get_value("Customer", {"name": cust_name}, "name")
    if not customer:
        try:
            cdoc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cust_name,
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
                "default_currency": curr,
                "custom_quickbooks_customer_id": cust_id
            })
            cdoc.flags.ignore_mandatory = True
            cdoc.flags.ignore_permissions = True
            cdoc.insert(ignore_permissions=True)
            customer = cdoc.name
        except Exception:
            customer = frappe.db.get_value("Customer", {}, "name") or cust_name
    return customer


def get_or_create_supplier(vendor_ref, curr="NGN"):
    if not vendor_ref:
        return frappe.db.get_value("Supplier", {}, "name") or "QuickBooks Supplier"
    vendor_id = vendor_ref.get("value")
    vendor_name = vendor_ref.get("name") or f"QuickBooks Vendor {vendor_id}"

    supplier = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": vendor_id}, "name") if vendor_id else None
    if not supplier and vendor_name:
        supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name") or \
                   frappe.db.get_value("Supplier", {"supplier_name": ["like", f"%{vendor_name}%"]}, "name") or \
                   frappe.db.get_value("Supplier", {"name": vendor_name}, "name")
    if not supplier:
        try:
            sdoc = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": vendor_name,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Private Limited Company(Ltd)",
                "default_currency": curr,
                "custom_quickbooks_vendor_id": vendor_id
            })
            sdoc.flags.ignore_mandatory = True
            sdoc.flags.ignore_permissions = True
            sdoc.insert(ignore_permissions=True)
            supplier = sdoc.name
        except Exception:
            supplier = frappe.db.get_value("Supplier", {}, "name") or vendor_name
    return supplier


# =============================================================================
# 1. TRANSFERS SYNC (155 records)
# =============================================================================
@frappe.whitelist()
def enqueue_sync_transfers():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.banking_and_returns_sync.sync_quickbooks_transfers",
        queue="long",
        timeout=3600,
        is_async=True,
        user=user
    )
    return "Transfers sync started in background."


@frappe.whitelist()
def sync_quickbooks_transfers(user=None):
    try:
        frappe.flags.in_import = True
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"

        all_transfers = []
        start = 1
        max_results = 500

        while True:
            q = f"SELECT * FROM Transfer STARTPOSITION {start} MAXRESULTS {max_results}"
            r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if not token:
                    return "Error: Token refresh failed."
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code != 200:
                break
            batch = r.json().get("QueryResponse", {}).get("Transfer", [])
            if not batch:
                break
            all_transfers.extend(batch)
            if len(batch) < max_results:
                break
            start += max_results

        total = len(all_transfers)
        created, updated, files_count = 0, 0, 0

        for idx, tr in enumerate(all_transfers, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                return f"Transfers sync stopped. Processed {created + updated} records."

            qb_id = tr.get("Id")
            tot_amt = flt(tr.get("Amount", 0))
            if tot_amt <= 0:
                continue

            txn_date = tr.get("TxnDate") or nowdate()
            curr = (tr.get("CurrencyRef", {}) or {}).get("value") or company_currency
            rate = flt(tr.get("ExchangeRate") or 1)
            if rate <= 0:
                rate = 1.0

            from_acc_ref = tr.get("FromAccountRef", {}) or {}
            to_acc_ref = tr.get("ToAccountRef", {}) or {}

            from_account = resolve_bank_account(from_acc_ref, curr, company)
            to_account = resolve_bank_account(to_acc_ref, curr, company)

            from_curr = frappe.db.get_value("Account", from_account, "account_currency") or company_currency
            to_curr = frappe.db.get_value("Account", to_account, "account_currency") or company_currency

            from_amt = tot_amt
            from_rate = rate
            if from_curr == "NGN" and curr == "USD":
                from_amt = round(tot_amt * rate, 2)
                from_rate = 1.0

            to_amt = tot_amt
            to_rate = rate
            if to_curr == "NGN" and curr == "USD":
                to_amt = round(tot_amt * rate, 2)
                to_rate = 1.0

            custom_id = f"TRF-{qb_id}"
            ref_no = f"TRF-{qb_id}"
            note = tr.get("PrivateNote") or f"QuickBooks Transfer {qb_id}"

            to_acc_type = frappe.db.get_value("Account", to_account, "account_type")
            from_acc_type = frappe.db.get_value("Account", from_account, "account_type")

            to_entry = {
                "account": to_account,
                "debit_in_account_currency": round(flt(to_amt), 2),
                "credit_in_account_currency": 0,
                "exchange_rate": to_rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": note[:140],
            }
            if to_acc_type == "Receivable":
                to_entry["party_type"] = "Customer"
                to_entry["party"] = get_or_create_customer(None, curr)
            elif to_acc_type == "Payable":
                to_entry["party_type"] = "Supplier"
                to_entry["party"] = get_or_create_supplier(None, curr)

            from_entry = {
                "account": from_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": round(flt(from_amt), 2),
                "exchange_rate": from_rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": note[:140],
            }
            if from_acc_type == "Receivable":
                from_entry["party_type"] = "Customer"
                from_entry["party"] = get_or_create_customer(None, curr)
            elif from_acc_type == "Payable":
                from_entry["party_type"] = "Supplier"
                from_entry["party"] = get_or_create_supplier(None, curr)

            accounts = [to_entry, from_entry]

            existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if existing_je:
                je = frappe.get_doc("Journal Entry", existing_je)
                if je.docstatus == 0:
                    je.accounts = []
                    for a in accounts:
                        je.append("accounts", a)
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
                    updated += 1
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
                    "custom_quickbooks_je_id": custom_id,
                    "user_remark": note[:140],
                    "_user_tags": ",QB Transfers,"
                })
                je.flags.ignore_permissions = True
                je.flags.ignore_mandatory = True
                je.flags.ignore_links = True
                je.insert(ignore_permissions=True)
                je.flags.ignore_permissions = True
                je.submit()
                created += 1
                je_name = je.name

            tag_journal_entry(je_name, "QB Transfers")
            files_count += fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, "QB_Transfer")

            if (created + updated) % 25 == 0:
                frappe.db.commit()

        frappe.db.commit()
        msg = f"Transfers Sync Completed: {created} created, {updated} updated, {files_count} files attached (Total: {total})."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QB Transfer Sync Error")
        return f"Error: {str(e)}"


# =============================================================================
# 2. CREDIT MEMOS SYNC (156 records - Sales Returns)
# =============================================================================
@frappe.whitelist()
def enqueue_sync_credit_memos():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.banking_and_returns_sync.sync_quickbooks_credit_memos",
        queue="long",
        timeout=3600,
        is_async=True,
        user=user
    )
    return "Credit Memos sync started in background."


@frappe.whitelist()
def sync_quickbooks_credit_memos(user=None):
    try:
        frappe.flags.in_import = True
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"
        default_income = "311010 - Revenue - SAAS - MTL"
        default_ar = "121010 - Trade Receivables - NGN - MTL"

        all_cms = []
        start = 1
        max_results = 500

        while True:
            q = f"SELECT * FROM CreditMemo STARTPOSITION {start} MAXRESULTS {max_results}"
            r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if not token:
                    return "Error: Token refresh failed."
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code != 200:
                break
            batch = r.json().get("QueryResponse", {}).get("CreditMemo", [])
            if not batch:
                break
            all_cms.extend(batch)
            if len(batch) < max_results:
                break
            start += max_results

        total = len(all_cms)
        created, updated, files_count = 0, 0, 0

        for idx, cm in enumerate(all_cms, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                return f"Credit Memos sync stopped. Processed {created + updated} records."

            qb_id = cm.get("Id")
            doc_no = cm.get("DocNumber")
            tot_amt = flt(cm.get("TotalAmt", 0))
            if tot_amt <= 0:
                continue

            txn_date = cm.get("TxnDate") or nowdate()
            curr = (cm.get("CurrencyRef", {}) or {}).get("value") or company_currency
            rate = flt(cm.get("ExchangeRate") or 1)
            if rate <= 0:
                rate = 1.0

            cust_ref = cm.get("CustomerRef", {}) or {}
            customer = get_or_create_customer(cust_ref, curr)

            cust_curr = frappe.db.get_value("Customer", customer, "default_currency") or curr
            receivable_account = "121020 - Trade Receivables - USD - MTL" if (cust_curr == "USD" or curr == "USD") else default_ar

            accounts = []
            total_debit = 0.0

            # Line items (Debits to Income/Tax/Expense)
            lines = cm.get("Line", []) or []
            for line in lines:
                if line.get("DetailType") == "SubTotalLineDetail":
                    continue
                amt = flt(line.get("Amount", 0), 2)
                if amt <= 0:
                    continue

                detail = line.get("SalesItemLineDetail", {}) or {}
                item_acc_ref = detail.get("ItemAccountRef") or detail.get("AccountRef") or {}
                income_acc = resolve_account_from_ref(item_acc_ref, company, default_income)

                desc = line.get("Description") or f"Credit Memo {doc_no or qb_id}"
                acc_type = frappe.db.get_value("Account", income_acc, "account_type")
                entry = {
                    "account": income_acc,
                    "debit_in_account_currency": amt,
                    "credit_in_account_currency": 0,
                    "exchange_rate": rate,
                    "cost_center": "QuickBooks - MTL",
                    "channel": "QuickBooks",
                    "department": "QuickBooks - MTL",
                    "user_remark": desc[:140],
                }
                if acc_type in ["Receivable", "Payable"]:
                    entry["party_type"] = "Customer"
                    entry["party"] = customer

                accounts.append(entry)
                total_debit += amt

            # Add Tax Line if tax amount exists
            tax_detail = cm.get("TxnTaxDetail", {}) or {}
            tax_amt = flt(tax_detail.get("TotalTax", 0), 2)
            if tax_amt > 0:
                vat_acc = "230040 - VAT Payable - MTL"
                accounts.append({
                    "account": vat_acc,
                    "debit_in_account_currency": tax_amt,
                    "credit_in_account_currency": 0,
                    "exchange_rate": rate,
                    "cost_center": "QuickBooks - MTL",
                    "channel": "QuickBooks",
                    "department": "QuickBooks - MTL",
                    "user_remark": f"VAT Credit Memo {doc_no or qb_id}",
                })
                total_debit += tax_amt

            if not accounts or total_debit <= 0:
                continue

            # Credit to Trade Receivables
            accounts.append({
                "account": receivable_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": round(total_debit, 2),
                "party_type": "Customer",
                "party": customer,
                "exchange_rate": rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": f"Credit Memo {doc_no or qb_id}",
            })

            custom_id = f"CM-{qb_id}"
            ref_no = f"CN-{doc_no}" if doc_no and len(str(doc_no)) >= 3 else f"CM-{qb_id}"

            existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if existing_je:
                je = frappe.get_doc("Journal Entry", existing_je)
                if je.docstatus == 0:
                    je.accounts = []
                    for a in accounts:
                        je.append("accounts", a)
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
                    updated += 1
                    je_name = je.name
                else:
                    je_name = existing_je
            else:
                je = frappe.get_doc({
                    "doctype": "Journal Entry",
                    "voucher_type": "Credit Note",
                    "company": company,
                    "posting_date": getdate(txn_date),
                    "cheque_no": ref_no,
                    "cheque_date": getdate(txn_date),
                    "multi_currency": 1,
                    "accounts": accounts,
                    "custom_quickbooks_je_id": custom_id,
                    "user_remark": f"credit memo of QBO - {doc_no or qb_id}",
                    "party_type": "Customer",
                    "party": customer,
                    "_user_tags": ",QB Credit Notes,"
                })
                je.flags.ignore_permissions = True
                je.flags.ignore_mandatory = True
                je.flags.ignore_links = True
                je.insert(ignore_permissions=True)
                je.flags.ignore_permissions = True
                je.submit()
                created += 1
                je_name = je.name

            tag_journal_entry(je_name, "QB Credit Notes")
            files_count += fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, "QB_CreditMemo")

            if (created + updated) % 25 == 0:
                frappe.db.commit()

        frappe.db.commit()
        msg = f"Credit Memos Sync Completed: {created} created, {updated} updated, {files_count} files attached (Total: {total})."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QB Credit Memo Sync Error")
        return f"Error: {str(e)}"


# =============================================================================
# 3. DEPOSITS SYNC (123 records - Bank Deposits)
# =============================================================================
@frappe.whitelist()
def enqueue_sync_deposits():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.banking_and_returns_sync.sync_quickbooks_deposits",
        queue="long",
        timeout=3600,
        is_async=True,
        user=user
    )
    return "Deposits sync started in background."


@frappe.whitelist()
def sync_quickbooks_deposits(user=None):
    try:
        frappe.flags.in_import = True
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"
        default_deposit_source = "312060 - Other Income - MTL"

        all_deposits = []
        start = 1
        max_results = 500

        while True:
            q = f"SELECT * FROM Deposit STARTPOSITION {start} MAXRESULTS {max_results}"
            r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if not token:
                    return "Error: Token refresh failed."
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code != 200:
                break
            batch = r.json().get("QueryResponse", {}).get("Deposit", [])
            if not batch:
                break
            all_deposits.extend(batch)
            if len(batch) < max_results:
                break
            start += max_results

        total = len(all_deposits)
        created, updated, files_count = 0, 0, 0

        for idx, dep in enumerate(all_deposits, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                return f"Deposits sync stopped. Processed {created + updated} records."

            qb_id = dep.get("Id")
            tot_amt = flt(dep.get("TotalAmt", 0))
            if tot_amt <= 0:
                continue

            txn_date = dep.get("TxnDate") or nowdate()
            curr = (dep.get("CurrencyRef", {}) or {}).get("value") or company_currency
            rate = flt(dep.get("ExchangeRate") or 1)
            if rate <= 0:
                rate = 1.0

            bank_ref = dep.get("DepositToAccountRef", {}) or {}
            bank_account = resolve_bank_account(bank_ref, curr, company)

            accounts = []
            total_credit = 0.0

            # Line items (Credits to Source Accounts)
            lines = dep.get("Line", []) or []
            for line in lines:
                amt = flt(line.get("Amount", 0), 2)
                if amt <= 0:
                    continue

                detail = line.get("DepositLineDetail", {}) or {}
                source_acc_ref = detail.get("AccountRef", {}) or {}
                source_acc = resolve_account_from_ref(source_acc_ref, company, default_deposit_source)

                # Check if account is Receivable or Payable
                acc_type = frappe.db.get_value("Account", source_acc, "account_type")
                entity_ref = detail.get("Entity", {}) or {}
                entity_val = entity_ref.get("EntityRef", {}) or {}

                source_curr = frappe.db.get_value("Account", source_acc, "account_currency") or company_currency
                line_rate = rate
                line_amt = amt
                if source_curr == "NGN" and curr == "USD":
                    line_amt = round(amt * rate, 2)
                    line_rate = 1.0
                elif source_curr == "USD" and curr == "NGN":
                    line_amt = round(amt / rate, 2)
                    line_rate = rate

                desc = line.get("Description") or dep.get("PrivateNote") or f"Deposit {qb_id}"
                
                if line_amt > 0:
                    deb_val = 0
                    crd_val = line_amt
                    total_credit += round(line_amt * line_rate, 2)
                else:
                    deb_val = abs(line_amt)
                    crd_val = 0
                    total_credit -= round(abs(line_amt) * line_rate, 2)

                entry = {
                    "account": source_acc,
                    "debit_in_account_currency": deb_val,
                    "credit_in_account_currency": crd_val,
                    "exchange_rate": line_rate,
                    "cost_center": "QuickBooks - MTL",
                    "channel": "QuickBooks",
                    "department": "QuickBooks - MTL",
                    "user_remark": str(desc)[:140],
                }

                if acc_type == "Receivable":
                    entry["party_type"] = "Customer"
                    entry["party"] = get_or_create_customer(entity_val, curr)
                elif acc_type == "Payable":
                    entry["party_type"] = "Supplier"
                    entry["party"] = get_or_create_supplier(entity_val, curr)

                accounts.append(entry)

            if not accounts or total_credit <= 0:
                continue

            bank_curr = frappe.db.get_value("Account", bank_account, "account_currency") or company_currency
            bank_rate = rate
            bank_amt = tot_amt
            if bank_curr == "NGN" and curr == "USD":
                bank_amt = round(tot_amt * rate, 2)
                bank_rate = 1.0

            # Debit to Bank Account
            bank_entry = {
                "account": bank_account,
                "debit_in_account_currency": round(bank_amt, 2),
                "credit_in_account_currency": 0,
                "exchange_rate": bank_rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": f"Deposit QBO - {qb_id}",
            }
            bank_acc_type = frappe.db.get_value("Account", bank_account, "account_type")
            if bank_acc_type == "Receivable":
                bank_entry["party_type"] = "Customer"
                bank_entry["party"] = get_or_create_customer(None, curr)
            elif bank_acc_type == "Payable":
                bank_entry["party_type"] = "Supplier"
                bank_entry["party"] = get_or_create_supplier(None, curr)

            accounts.insert(0, bank_entry)

            custom_id = f"DEP-{qb_id}"
            ref_no = f"DEP-{qb_id}"

            existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if existing_je:
                je = frappe.get_doc("Journal Entry", existing_je)
                if je.docstatus == 0:
                    je.accounts = []
                    for a in accounts:
                        je.append("accounts", a)
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
                    updated += 1
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
                    "custom_quickbooks_je_id": custom_id,
                    "user_remark": f"deposit of QBO - {qb_id}",
                    "_user_tags": ",QB Deposits,"
                })
                je.flags.ignore_permissions = True
                je.flags.ignore_mandatory = True
                je.flags.ignore_links = True
                je.insert(ignore_permissions=True)
                je.flags.ignore_permissions = True
                je.submit()
                created += 1
                je_name = je.name

            tag_journal_entry(je_name, "QB Deposits")
            files_count += fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, "QB_Deposit")

            if (created + updated) % 25 == 0:
                frappe.db.commit()

        frappe.db.commit()
        msg = f"Deposits Sync Completed: {created} created, {updated} updated, {files_count} files attached (Total: {total})."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QB Deposit Sync Error")
        return f"Error: {str(e)}"


# =============================================================================
# 4. VENDOR CREDITS SYNC (20 records - Purchase Returns)
# =============================================================================
@frappe.whitelist()
def enqueue_sync_vendor_credits():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.banking_and_returns_sync.sync_quickbooks_vendor_credits",
        queue="long",
        timeout=3600,
        is_async=True,
        user=user
    )
    return "Vendor Credits sync started in background."


@frappe.whitelist()
def sync_quickbooks_vendor_credits(user=None):
    try:
        if not user and getattr(frappe, "session", None):
            user = frappe.session.user

        settings = frappe.get_single("Quickbook Settings")
        access_token = settings.access_token
        realm_id = settings.realm_id
        environment = settings.environment or "sandbox"
        base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}

        company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
        company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"
        default_expense = "403320 - Office Expenses - MTL"
        default_payable = "225010 - Trade Creditors - NGN - MTL"

        all_vcs = []
        start = 1
        max_results = 500

        while True:
            q = f"SELECT * FROM VendorCredit STARTPOSITION {start} MAXRESULTS {max_results}"
            r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if not token:
                    return "Error: Token refresh failed."
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code != 200:
                break
            batch = r.json().get("QueryResponse", {}).get("VendorCredit", [])
            if not batch:
                break
            all_vcs.extend(batch)
            if len(batch) < max_results:
                break
            start += max_results

        total = len(all_vcs)
        created, updated, files_count = 0, 0, 0

        for idx, vc in enumerate(all_vcs, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                return f"Vendor Credits sync stopped. Processed {created + updated} records."

            qb_id = vc.get("Id")
            doc_no = vc.get("DocNumber")
            tot_amt = flt(vc.get("TotalAmt", 0))
            if tot_amt <= 0:
                continue

            txn_date = vc.get("TxnDate") or nowdate()
            curr = (vc.get("CurrencyRef", {}) or {}).get("value") or company_currency
            rate = flt(vc.get("ExchangeRate") or 1)
            if rate <= 0:
                rate = 1.0

            vendor_ref = vc.get("VendorRef", {}) or {}
            supplier = get_or_create_supplier(vendor_ref, curr)

            supp_curr = frappe.db.get_value("Supplier", supplier, "default_currency") or curr
            payable_account = "225020 - Trade Creditors - USD - MTL" if (supp_curr == "USD" or curr == "USD") else default_payable

            accounts = []
            total_credit = 0.0

            # Line items (Credits to Expense Accounts)
            lines = vc.get("Line", []) or []
            for line in lines:
                amt = flt(line.get("Amount", 0), 2)
                if amt <= 0:
                    continue

                detail = line.get("AccountBasedExpenseLineDetail", {}) or line.get("ItemBasedExpenseLineDetail", {}) or {}
                acc_ref = detail.get("AccountRef") or detail.get("ItemRef") or {}
                expense_acc = resolve_account_from_ref(acc_ref, company, default_expense)

                desc = line.get("Description") or f"Vendor Credit {doc_no or qb_id}"
                acc_type = frappe.db.get_value("Account", expense_acc, "account_type")
                entry = {
                    "account": expense_acc,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": amt,
                    "exchange_rate": rate,
                    "cost_center": "QuickBooks - MTL",
                    "channel": "QuickBooks",
                    "department": "QuickBooks - MTL",
                    "user_remark": desc[:140],
                }
                if acc_type in ["Payable", "Receivable"]:
                    entry["party_type"] = "Supplier"
                    entry["party"] = supplier

                accounts.append(entry)
                total_credit += amt

            if not accounts or total_credit <= 0:
                continue

            # Debit to Trade Creditors
            accounts.insert(0, {
                "account": payable_account,
                "debit_in_account_currency": round(total_credit, 2),
                "credit_in_account_currency": 0,
                "party_type": "Supplier",
                "party": supplier,
                "exchange_rate": rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": f"Vendor Credit {doc_no or qb_id}",
            })

            custom_id = f"VENDCRED-{qb_id}"
            ref_no = f"VC-{doc_no}" if doc_no and len(str(doc_no)) >= 3 else f"VENDCRED-{qb_id}"

            existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if existing_je:
                je = frappe.get_doc("Journal Entry", existing_je)
                if je.docstatus == 0:
                    je.accounts = []
                    for a in accounts:
                        je.append("accounts", a)
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
                    updated += 1
                    je_name = je.name
                else:
                    je_name = existing_je
            else:
                je = frappe.get_doc({
                    "doctype": "Journal Entry",
                    "voucher_type": "Debit Note",
                    "company": company,
                    "posting_date": getdate(txn_date),
                    "cheque_no": ref_no,
                    "cheque_date": getdate(txn_date),
                    "multi_currency": 1,
                    "accounts": accounts,
                    "custom_quickbooks_je_id": custom_id,
                    "user_remark": f"vendor credit of QBO - {doc_no or qb_id}",
                    "party_type": "Supplier",
                    "party": supplier,
                    "_user_tags": ",QB Vendor Credits,"
                })
                je.flags.ignore_permissions = True
                je.flags.ignore_mandatory = True
                je.flags.ignore_links = True
                je.insert(ignore_permissions=True)
                je.flags.ignore_permissions = True
                je.submit()
                created += 1
                je_name = je.name

            tag_journal_entry(je_name, "QB Vendor Credits")
            files_count += fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, "QB_VendorCredit")

            if (created + updated) % 25 == 0:
                frappe.db.commit()

        frappe.db.commit()
        msg = f"Vendor Credits Sync Completed: {created} created, {updated} updated, {files_count} files attached (Total: {total})."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QB Vendor Credit Sync Error")
        return f"Error: {str(e)}"


# =============================================================================
# 5. ALL AUXILIARY SYNC (1-Click Sync for Transfers, Credits, Deposits)
# =============================================================================
@frappe.whitelist()
def enqueue_sync_all_auxiliary():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.banking_and_returns_sync.sync_all_auxiliary_transactions",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "All Auxiliary Transactions sync (Transfers, Credits, Deposits) started in background."


@frappe.whitelist()
def sync_all_auxiliary_transactions(user=None):
    r1 = sync_quickbooks_transfers(user=user)
    r2 = sync_quickbooks_credit_memos(user=user)
    r3 = sync_quickbooks_deposits(user=user)
    r4 = sync_quickbooks_vendor_credits(user=user)

    summary = f"Auxiliary Sync Summary:\n• {r1}\n• {r2}\n• {r3}\n• {r4}"
    if user:
        frappe.publish_realtime("msgprint", summary, user=user)
    return summary

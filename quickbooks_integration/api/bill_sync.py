import frappe
import requests
import json
from intuitlib.client import AuthClient
from frappe.utils import getdate, nowdate, flt


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


def adjust_due_date_for_je(posting_date, due_date):
    posting_date = getdate(posting_date or nowdate())
    due_date = getdate(due_date or posting_date)
    if due_date < posting_date:
        due_date = posting_date
    return posting_date, due_date


from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache


def get_expense_account_for_line(line, company, default_expense):
    """Resolve the ERPNext Account using Centralized Account Mapper"""
    acc_detail = line.get("AccountBasedExpenseLineDetail", {}) or {}
    item_detail = line.get("ItemBasedExpenseLineDetail", {}) or {}

    acc_ref = acc_detail.get("AccountRef", {}) or item_detail.get("ItemRef", {}) or {}
    if acc_ref:
        return resolve_account_master(acc_ref, company, default_acc=default_expense)

    return default_expense


def fetch_bill_attachments(bill_id, je_name, headers, base_url, realm_id):
    """Fetch and attach all files from QuickBooks Attachable for a Bill"""
    try:
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{bill_id}'"
        res = requests.post(endpoint, headers=headers, data=query, timeout=30)
        if res.status_code != 200:
            return 0

        attachables = res.json().get("QueryResponse", {}).get("Attachable", [])
        attached_count = 0

        for att in attachables:
            file_name = att.get("FileName") or f"QB_Bill_Attachment_{att.get('Id')}.bin"
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
        frappe.log_error(f"Error fetching attachments for bill {bill_id}: {str(e)}", "QB Bill Attachment Sync")
        return 0


@frappe.whitelist()
def enqueue_sync_bills():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.bill_sync.sync_quickbooks_bills",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "Bills sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def sync_quickbooks_bills(user=None):
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

        default_expense = frappe.get_cached_value("Company", company, "default_expense_account") or "403320 - Office Expenses - MTL"
        default_payable = frappe.get_cached_value("Company", company, "default_payable_account") or "225010 - Trade Creditors - NGN - MTL"
        default_cost_center = "QuickBooks - MTL"
        default_channel = "QuickBooks"
        default_department = "QuickBooks - MTL"

        all_bills = []
        start_position = 1
        max_results = 500

        while True:
            query = f"SELECT * FROM Bill STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Bill Sync API Error")
                break

            data = response.json()
            bills_batch = data.get("QueryResponse", {}).get("Bill", [])
            if not bills_batch:
                break

            all_bills.extend(bills_batch)
            if len(bills_batch) < max_results:
                break
            start_position += max_results

        if not all_bills:
            return "No bills found in QuickBooks."

        total_bills = len(all_bills)
        created_je, updated_je, total_attachments = 0, 0, 0
        skipped = []

        for idx, b in enumerate(all_bills, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Bill sync stopped by user. Processed {created_je + updated_je} bills."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 25 == 0 or idx == total_bills:
                try:
                    frappe.publish_progress(
                        percent=round((idx / max(total_bills, 1)) * 100),
                        title="Syncing Bills",
                        description=f"Processing bill {idx} of {total_bills}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = b.get("Id")
                bill_no = b.get("DocNumber")
                vendor_ref = b.get("VendorRef", {}) or {}
                vendor_id = vendor_ref.get("value")
                vendor_name = vendor_ref.get("name") or f"QuickBooks Vendor {vendor_id}"

                raw_txn_date = b.get("TxnDate") or nowdate()
                raw_due_date = b.get("DueDate") or raw_txn_date
                currency = (b.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(b.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Supplier mapping
                supplier = None
                if vendor_id:
                    supplier = frappe.db.get_value("Supplier", {"custom_quickbooks_vendor_id": vendor_id}, "name")
                if not supplier and vendor_name:
                    supplier = frappe.db.get_value("Supplier", {"supplier_name": vendor_name}, "name") or \
                               frappe.db.get_value("Supplier", {"name": vendor_name}, "name")
                if not supplier:
                    try:
                        supp_doc = frappe.get_doc({
                            "doctype": "Supplier",
                            "supplier_name": vendor_name,
                            "supplier_group": "All Supplier Groups",
                            "supplier_type": "Private Limited Company(Ltd)",
                            "default_currency": currency,
                            "custom_quickbooks_vendor_id": vendor_id
                        })
                        supp_doc.flags.ignore_mandatory = True
                        supp_doc.insert(ignore_permissions=True)
                        supplier = supp_doc.name
                    except Exception:
                        supplier = vendor_name

                lines = b.get("Line", []) or []
                accounts = []
                total_credit = 0.0
                has_depreciation_account = False

                for line in lines:
                    amount = flt(line.get("Amount", 0), 2)
                    if not amount or amount <= 0:
                        continue

                    expense_account = get_expense_account_for_line(line, company, default_expense)
                    if not expense_account:
                        expense_account = default_expense

                    acc_type = frappe.db.get_value("Account", expense_account, "account_type")
                    if acc_type == "Accumulated Depreciation":
                        has_depreciation_account = True

                    desc = line.get("Description") or "QuickBooks Bill Line"

                    acc_entry = {
                        "account": expense_account,
                        "debit_in_account_currency": amount,
                        "credit_in_account_currency": 0,
                        "exchange_rate": exchange_rate,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else "bills of QBO",
                    }

                    if acc_type in ["Payable", "Receivable"]:
                        acc_entry["party_type"] = "Supplier"
                        acc_entry["party"] = supplier

                    accounts.append(acc_entry)
                    total_credit += amount

                if not accounts or total_credit <= 0:
                    skipped.append(f"Bill {bill_no or qb_id} skipped - No valid debit amounts")
                    continue

                supp_curr = frappe.db.get_value("Supplier", supplier, "default_currency") or currency
                payable_account = "225020 - Trade Creditors - USD - MTL" if (supp_curr == "USD" or currency == "USD") else default_payable

                party_acc_entry = {
                    "account": payable_account,
                    "credit_in_account_currency": round(total_credit, 2),
                    "debit_in_account_currency": 0,
                    "party_type": "Supplier",
                    "party": supplier,
                    "cost_center": default_cost_center,
                    "channel": default_channel,
                    "department": default_department,
                    "exchange_rate": exchange_rate,
                    "user_remark": f"QuickBooks Bill {bill_no or qb_id}",
                }
                accounts.append(party_acc_entry)

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                cheque_ref = bill_no if bill_no and len(str(bill_no)) >= 3 else f"BILL-{bill_no or qb_id}"
                existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": qb_id}, "name")
                voucher_type = "Depreciation Entry" if has_depreciation_account else "Journal Entry"

                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    if je.docstatus == 0:
                        je.voucher_type = voucher_type
                        je.accounts = []
                        for acc in accounts:
                            je.append("accounts", acc)
                        je.posting_date = posting_date
                        je.cheque_no = cheque_ref
                        je.cheque_date = cheque_date
                        je.multi_currency = 1
                        je.flags.ignore_permissions = True
                        je.flags.ignore_mandatory = True
                        je.flags.ignore_links = True
                        je.save(ignore_permissions=True)
                        je.flags.ignore_permissions = True
                        je.submit()
                        updated_je += 1
                        je_name = je.name
                    else:
                        je_name = existing_je
                else:
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "voucher_type": voucher_type,
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": cheque_ref,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": qb_id,
                        "user_remark": f"bills of QBO - {bill_no or qb_id}",
                        "party_type": "Supplier",
                        "party": supplier,
                        "_user_tags": ",QB Bills,"
                    })
                    je.flags.ignore_permissions = True
                    je.flags.ignore_mandatory = True
                    je.flags.ignore_links = True
                    je.insert(ignore_permissions=True)
                    je.flags.ignore_permissions = True
                    je.submit()
                    created_je += 1
                    je_name = je.name

                # Add Tag
                try:
                    frappe.db.set_value("Journal Entry", je_name, "_user_tags", ",QB Bills,")
                    if not frappe.db.exists("Tag", "QB Bills"):
                        frappe.get_doc({"doctype": "Tag", "name": "QB Bills"}).insert(ignore_permissions=True)
                    if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": "QB Bills"}):
                        frappe.get_doc({
                            "doctype": "Tag Link",
                            "document_type": "Journal Entry",
                            "document_name": je_name,
                            "tag": "QB Bills"
                        }).insert(ignore_permissions=True)
                except Exception:
                    pass

                # Attachments
                att_count = fetch_bill_attachments(qb_id, je_name, headers, base_url, realm_id)
                total_attachments += att_count

                if (created_je + updated_je) % 50 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"Bill {b.get('DocNumber') or b.get('Id')} skipped: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"Bills Sync Completed: {created_je} created, {updated_je} updated, {total_attachments} files attached (Total processed: {len(all_bills)})."
        if skipped:
            msg += f" Skipped {len(skipped)} entries."
            frappe.log_error("\n".join(skipped), "QuickBooks Bill Sync Skipped")

        if user:
            frappe.publish_realtime("msgprint", msg, user=user)

        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Bill Sync Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

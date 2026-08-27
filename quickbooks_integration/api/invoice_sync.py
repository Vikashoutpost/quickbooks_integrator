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


def get_income_account_for_line(line, company, default_income):
    """Resolve the ERPNext Account for Sales Invoice lines"""
    detail = line.get("SalesItemLineDetail", {}) or {}
    item_ref = detail.get("ItemRef", {}) or {}
    item_name = item_ref.get("name")
    item_val = item_ref.get("value")

    # 1. Look up item's default income account in ERPNext
    if item_name:
        item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name") or \
                    frappe.db.get_value("Item", {"item_code": item_name}, "name") or \
                    frappe.db.get_value("Item", {"name": item_name}, "name")
        if item_code:
            income_acc = frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "income_account")
            if income_acc:
                return income_acc

        acc = frappe.db.get_value("Account", {"account_name": item_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"custom_qbc_child_account_name": item_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"name": ["like", f"%{item_name}%"], "company": company, "is_group": 0}, "name")
        if acc:
            return acc

    # 2. Check if line has direct AccountRef
    acc_ref = detail.get("AccountRef", {}) or {}
    acc_val = acc_ref.get("value")
    acc_name = acc_ref.get("name")

    if acc_val:
        acc = frappe.db.get_value("Account", {"account_number": f"QB-{acc_val}", "company": company}, "name")
        if acc:
            return acc

    if acc_name:
        acc = frappe.db.get_value("Account", {"account_name": acc_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"custom_qbc_child_account_name": acc_name, "company": company, "is_group": 0}, "name") or \
              frappe.db.get_value("Account", {"name": ["like", f"%{acc_name}%"], "company": company, "is_group": 0}, "name")
        if acc:
            return acc

    return default_income


def fetch_invoice_attachments(inv_id, je_name, headers, base_url, realm_id):
    """Fetch and attach all files from QuickBooks Attachable for an Invoice"""
    try:
        endpoint = f"{base_url}/v3/company/{realm_id}/query"
        query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{inv_id}'"
        res = requests.post(endpoint, headers=headers, data=query, timeout=30)
        if res.status_code != 200:
            return 0

        attachables = res.json().get("QueryResponse", {}).get("Attachable", [])
        attached_count = 0

        for att in attachables:
            file_name = att.get("FileName") or f"QB_Invoice_Attachment_{att.get('Id')}.bin"
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
        frappe.log_error(f"Error fetching attachments for invoice {inv_id}: {str(e)}", "QB Invoice Attachment Sync")
        return 0


@frappe.whitelist()
def enqueue_sync_invoices():
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.invoice_sync.sync_quickbooks_invoices",
        queue="long",
        timeout=7200,
        is_async=True,
        user=user
    )
    return "Invoices sync has started in the background. You will be notified when complete."


@frappe.whitelist()
def sync_quickbooks_invoices(user=None):
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

        default_income = frappe.get_cached_value("Company", company, "default_income_account") or "311010 - Revenue - SAAS - MTL"
        default_receivable = frappe.get_cached_value("Company", company, "default_receivable_account") or "121010 - Trade Receivables - NGN - MTL"
        default_cost_center = "QuickBooks - MTL"
        default_channel = "QuickBooks"
        default_department = "QuickBooks - MTL"

        all_invoices = []
        start_position = 1
        max_results = 500

        while True:
            query = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}"
            response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code == 401:
                new_token = refresh_qb_token(settings)
                if not new_token:
                    return "Error: Failed to refresh QuickBooks OAuth token."
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(endpoint, headers=headers, data=query, timeout=60)

            if response.status_code != 200:
                frappe.log_error(response.text, "QuickBooks Invoice Sync API Error")
                break

            data = response.json()
            batch = data.get("QueryResponse", {}).get("Invoice", [])
            if not batch:
                break

            all_invoices.extend(batch)
            if len(batch) < max_results:
                break
            start_position += max_results

        if not all_invoices:
            return "No invoices found in QuickBooks."

        total_invoices = len(all_invoices)
        created_je, updated_je, total_attachments = 0, 0, 0
        skipped = []

        for idx, inv in enumerate(all_invoices, 1):
            if idx % 10 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                msg = f"Invoices sync stopped by user. Processed {created_je + updated_je} invoices."
                if user:
                    frappe.publish_realtime("msgprint", msg, user=user)
                return msg

            if idx % 25 == 0 or idx == total_invoices:
                try:
                    frappe.publish_progress(
                        percent=round((idx / max(total_invoices, 1)) * 100),
                        title="Syncing Invoices",
                        description=f"Processing invoice {idx} of {total_invoices}...",
                        user=user
                    )
                except Exception:
                    pass

            try:
                qb_id = inv.get("Id")
                inv_no = inv.get("DocNumber")
                cust_ref = inv.get("CustomerRef", {}) or {}
                cust_id = cust_ref.get("value")
                cust_name = cust_ref.get("name") or f"QuickBooks Customer {cust_id}"

                raw_txn_date = inv.get("TxnDate") or nowdate()
                raw_due_date = inv.get("DueDate") or raw_txn_date
                currency = (inv.get("CurrencyRef", {}) or {}).get("value") or company_currency
                exchange_rate = flt(inv.get("ExchangeRate") or 1)
                if exchange_rate <= 0:
                    exchange_rate = 1

                # Customer mapping
                customer = None
                if cust_id:
                    customer = frappe.db.get_value("Customer", {"custom_quickbooks_customer_id": cust_id}, "name")
                if not customer and cust_name:
                    customer = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name") or \
                               frappe.db.get_value("Customer", {"name": cust_name}, "name")
                if not customer:
                    try:
                        cdoc = frappe.get_doc({
                            "doctype": "Customer",
                            "customer_name": cust_name,
                            "customer_group": "All Customer Groups",
                            "territory": "All Territories",
                            "default_currency": currency,
                            "custom_quickbooks_customer_id": cust_id
                        })
                        cdoc.flags.ignore_mandatory = True
                        cdoc.insert(ignore_permissions=True)
                        customer = cdoc.name
                    except Exception:
                        customer = cust_name

                lines = inv.get("Line", []) or []
                accounts = []
                total_debit = 0.0

                for line in lines:
                    detail_type = line.get("DetailType")
                    if detail_type not in ["SalesItemLineDetail", "GroupLineDetail"]:
                        continue

                    amount = flt(line.get("Amount", 0), 2)
                    if not amount or amount <= 0:
                        continue

                    income_account = get_income_account_for_line(line, company, default_income)
                    if not income_account:
                        income_account = default_income

                    desc = line.get("Description") or "QuickBooks Invoice Line"

                    acc_entry = {
                        "account": income_account,
                        "credit_in_account_currency": amount,
                        "debit_in_account_currency": 0,
                        "exchange_rate": exchange_rate,
                        "cost_center": default_cost_center,
                        "channel": default_channel,
                        "department": default_department,
                        "user_remark": desc[:140] if desc else "sales of QBO",
                    }
                    accounts.append(acc_entry)
                    total_debit += amount

                if not accounts or total_debit <= 0:
                    skipped.append(f"Invoice {inv_no or qb_id} skipped - No valid credit amounts")
                    continue

                cust_curr = frappe.db.get_value("Customer", customer, "default_currency") or currency
                receivable_account = "121020 - Trade Receivables - USD - MTL" if (cust_curr == "USD" or currency == "USD") else default_receivable

                receivable_acc_entry = {
                    "account": receivable_account,
                    "debit_in_account_currency": round(total_debit, 2),
                    "credit_in_account_currency": 0,
                    "party_type": "Customer",
                    "party": customer,
                    "cost_center": default_cost_center,
                    "channel": default_channel,
                    "department": default_department,
                    "exchange_rate": exchange_rate,
                    "user_remark": f"QuickBooks Invoice {inv_no or qb_id}",
                }
                accounts.insert(0, receivable_acc_entry)

                posting_date, cheque_date = adjust_due_date_for_je(raw_txn_date, raw_due_date)
                cheque_ref = inv_no if inv_no and len(str(inv_no)) >= 3 else f"INV-{inv_no or qb_id}"
                custom_je_id = f"INV-{qb_id}"
                existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_je_id}, "name")

                if existing_je:
                    je = frappe.get_doc("Journal Entry", existing_je)
                    if je.docstatus == 0:
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
                        "voucher_type": "Journal Entry",
                        "company": company,
                        "posting_date": posting_date,
                        "cheque_no": cheque_ref,
                        "cheque_date": cheque_date,
                        "multi_currency": 1,
                        "accounts": accounts,
                        "custom_quickbooks_je_id": custom_je_id,
                        "user_remark": f"sales of QBO - {inv_no or qb_id}",
                        "party_type": "Customer",
                        "party": customer,
                        "_user_tags": ",QB Sales,"
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
                    frappe.db.set_value("Journal Entry", je_name, "_user_tags", ",QB Sales,")
                    if not frappe.db.exists("Tag", "QB Sales"):
                        frappe.get_doc({"doctype": "Tag", "name": "QB Sales"}).insert(ignore_permissions=True)
                    if not frappe.db.exists("Tag Link", {"document_type": "Journal Entry", "document_name": je_name, "tag": "QB Sales"}):
                        frappe.get_doc({
                            "doctype": "Tag Link",
                            "document_type": "Journal Entry",
                            "document_name": je_name,
                            "tag": "QB Sales"
                        }).insert(ignore_permissions=True)
                except Exception:
                    pass

                # Attachments
                att_count = fetch_invoice_attachments(qb_id, je_name, headers, base_url, realm_id)
                total_attachments += att_count

                if (created_je + updated_je) % 50 == 0:
                    frappe.db.commit()

            except Exception as inner_e:
                skipped.append(f"Invoice {inv.get('DocNumber') or inv.get('Id')} skipped: {str(inner_e)}")
                continue

        frappe.db.commit()
        msg = f"Invoices Sync Completed: {created_je} created, {updated_je} updated, {total_attachments} files attached (Total processed: {len(all_invoices)})."
        if skipped:
            msg += f" Skipped {len(skipped)} entries."
            frappe.log_error("\n".join(skipped), "QuickBooks Invoice Sync Skipped")

        if user:
            frappe.publish_realtime("msgprint", msg, user=user)

        return msg

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Invoice Sync Error")
        err_msg = f"Error occurred: {str(e)}"
        if user:
            frappe.publish_realtime("msgprint", err_msg, user=user)
        return err_msg

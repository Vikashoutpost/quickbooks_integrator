import frappe
import requests
from intuitlib.client import AuthClient
from frappe.utils import nowdate, getdate, flt
from quickbooks_integration.api.payments_sync import BANK_MAP, resolve_bank_account
from quickbooks_integration.api.banking_and_returns_sync import (
    refresh_qb_token, resolve_account_from_ref, get_or_create_customer,
    get_or_create_supplier, tag_journal_entry, fetch_entity_attachments
)


def build_account_cache(company):
    """Pre-load all accounts for instant O(1) in-memory resolution without DB hits"""
    accounts = frappe.db.sql("""
        SELECT name, account_name, account_number, account_currency, account_type, custom_qbc_child_account_name
        FROM `tabAccount`
        WHERE company = %s AND is_group = 0
    """, (company,), as_dict=True)

    cache = {
        "by_name": {},
        "by_acc_num": {},
        "by_qbc_name": {},
        "raw": {}
    }
    for a in accounts:
        cache["raw"][a.name] = a
        if a.account_name:
            cache["by_name"][a.account_name.lower().strip()] = a.name
        if a.account_number:
            cache["by_acc_num"][str(a.account_number).strip()] = a.name
        if a.custom_qbc_child_account_name:
            cache["by_qbc_name"][a.custom_qbc_child_account_name.lower().strip()] = a.name
    return cache


def fast_resolve_account(acc_ref, company, default_expense, cache):
    """Fast account resolution using in-memory cache"""
    if not acc_ref:
        return default_expense

    val = str(acc_ref.get("value") or "").strip()
    name = (acc_ref.get("name") or "").strip().lower()

    # 1. Exact Bank Map
    if val and val in BANK_MAP:
        return BANK_MAP[val]
    for k, v in BANK_MAP.items():
        if (name and k in name) or k == val:
            if v in cache["raw"]:
                return v

    # 2. Match from QB-{val}
    if val:
        qb_num = f"QB-{val}"
        if qb_num in cache["by_acc_num"]:
            return cache["by_acc_num"][qb_num]

    # 3. Match from Account Name
    if name:
        if name in cache["by_name"]:
            return cache["by_name"][name]
        if name in cache["by_qbc_name"]:
            return cache["by_qbc_name"][name]
        for acc_name, acc_id in cache["by_name"].items():
            if name in acc_name:
                return acc_id

    return default_expense if default_expense in cache["raw"] else "403320 - Office Expenses - MTL"


@frappe.whitelist()
def enqueue_sync_purchases(fetch_files=1):
    frappe.cache().delete_value("qb_sync_cancel_requested")
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.purchase_expenses_sync.sync_quickbooks_purchases",
        queue="long",
        timeout=14400,
        is_async=True,
        user=user,
        fetch_files=int(fetch_files)
    )
    return "Direct Expenses sync started in background."


@frappe.whitelist()
def sync_quickbooks_purchases(user=None, fetch_files=0):
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
        default_expense = "403320 - Office Expenses - MTL"
        cache = build_account_cache(company)

        all_purchases = []
        start = 1
        max_results = 1000

        while True:
            q = f"SELECT * FROM Purchase STARTPOSITION {start} MAXRESULTS {max_results}"
            r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if not token:
                    return "Error: Token refresh failed."
                headers["Authorization"] = f"Bearer {token}"
                r = requests.post(endpoint, headers=headers, data=q, timeout=60)
            if r.status_code != 200:
                break
            batch = r.json().get("QueryResponse", {}).get("Purchase", [])
            if not batch:
                break
            all_purchases.extend(batch)
            if len(batch) < max_results:
                break
            start += max_results

        total = len(all_purchases)
        created, updated, files_count = 0, 0, 0

        for idx, p in enumerate(all_purchases, 1):
            if idx % 20 == 0 and frappe.cache().get_value("qb_sync_cancel_requested"):
                frappe.cache().delete_value("qb_sync_cancel_requested")
                frappe.db.commit()
                return f"Direct Expenses sync stopped. Processed {created + updated} records."

            qb_id = p.get("Id")
            tot_amt = flt(p.get("TotalAmt", 0))
            if tot_amt <= 0:
                continue

            txn_date = p.get("TxnDate") or nowdate()
            curr = (p.get("CurrencyRef", {}) or {}).get("value") or company_currency
            rate = flt(p.get("ExchangeRate") or 1)
            if rate <= 0:
                rate = 1.0

            bank_ref = p.get("AccountRef", {}) or {}
            bank_account = resolve_bank_account(bank_ref, curr, company)

            entity_ref = p.get("EntityRef", {}) or {}
            entity_type = (entity_ref.get("type") or "Vendor").lower()
            supplier = None
            customer = None
            if entity_type == "customer":
                customer = get_or_create_customer(entity_ref, curr)
            else:
                supplier = get_or_create_supplier(entity_ref, curr)

            accounts = []
            total_debit = 0.0

            lines = p.get("Line", []) or []
            for line in lines:
                amt = flt(line.get("Amount", 0), 2)
                if amt == 0:
                    continue

                detail = line.get("AccountBasedExpenseLineDetail") or line.get("ItemBasedExpenseLineDetail") or {}
                acc_ref = detail.get("AccountRef") or detail.get("ItemRef") or {}
                expense_acc = fast_resolve_account(acc_ref, company, default_expense, cache)

                acc_info = cache["raw"].get(expense_acc, {})
                acc_curr = acc_info.get("account_currency") or company_currency
                acc_type = acc_info.get("account_type")

                line_rate = rate
                line_amt = amt
                if acc_curr == "NGN" and curr == "USD":
                    line_amt = round(amt * rate, 2)
                    line_rate = 1.0
                elif acc_curr == "USD" and curr == "NGN":
                    line_amt = round(amt / rate, 2)
                    line_rate = rate

                desc = line.get("Description") or p.get("PrivateNote") or f"Direct Expense {qb_id}"

                if line_amt > 0:
                    deb_val = line_amt
                    crd_val = 0
                    total_debit += round(line_amt * line_rate, 2)
                else:
                    deb_val = 0
                    crd_val = abs(line_amt)
                    total_debit -= round(abs(line_amt) * line_rate, 2)

                entry = {
                    "account": expense_acc,
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
                    entry["party"] = customer or get_or_create_customer(entity_ref, curr)
                elif acc_type == "Payable":
                    entry["party_type"] = "Supplier"
                    entry["party"] = supplier or get_or_create_supplier(entity_ref, curr)

                accounts.append(entry)

            # Tax Detail
            tax_detail = p.get("TxnTaxDetail", {}) or {}
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
                    "user_remark": f"VAT Direct Expense {qb_id}",
                })
                total_debit += round(tax_amt * rate, 2)

            if not accounts or total_debit <= 0:
                continue

            # Credit to Bank
            bank_info = cache["raw"].get(bank_account, {})
            bank_curr = bank_info.get("account_currency") or company_currency
            bank_rate = rate
            bank_amt = tot_amt
            if bank_curr == "NGN" and curr == "USD":
                bank_amt = round(tot_amt * rate, 2)
                bank_rate = 1.0

            bank_entry = {
                "account": bank_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": round(bank_amt, 2),
                "exchange_rate": bank_rate,
                "cost_center": "QuickBooks - MTL",
                "channel": "QuickBooks",
                "department": "QuickBooks - MTL",
                "user_remark": f"Expense QBO - {qb_id}",
            }
            bank_acc_type = bank_info.get("account_type")
            if bank_acc_type == "Receivable":
                bank_entry["party_type"] = "Customer"
                bank_entry["party"] = customer or get_or_create_customer(None, curr)
            elif bank_acc_type == "Payable":
                bank_entry["party_type"] = "Supplier"
                bank_entry["party"] = supplier or get_or_create_supplier(None, curr)

            accounts.append(bank_entry)

            custom_id = f"EXP-{qb_id}"
            doc_no = p.get("DocNumber")
            ref_no = f"EXP-{doc_no}" if doc_no and len(str(doc_no)) >= 3 else f"EXP-{qb_id}"
            note = p.get("PrivateNote") or f"Direct Expense QBO - {qb_id}"

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
                    "_user_tags": ",QB Expenses,"
                })
                je.flags.ignore_permissions = True
                je.flags.ignore_mandatory = True
                je.flags.ignore_links = True
                je.insert(ignore_permissions=True)
                je.flags.ignore_permissions = True
                je.submit()
                created += 1
                je_name = je.name

            tag_journal_entry(je_name, "QB Expenses")

            if fetch_files:
                files_count += fetch_entity_attachments(qb_id, je_name, headers, base_url, realm_id, "QB_Expense")

            if (created + updated) % 50 == 0:
                frappe.db.commit()

        frappe.db.commit()
        msg = f"Direct Expenses Sync Completed: {created} created, {updated} updated, {files_count} files attached (Total: {total})."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QB Direct Expenses Sync Error")
        return f"Error: {str(e)}"


@frappe.whitelist()
def sync_single_purchase_sample(purchase_id=None):
    """Sync exactly 1 sample Purchase record to test and verify line items, taxes, and GL entries"""
    frappe.flags.in_import = True
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}

    company = frappe.defaults.get_global_default("company") or "Movam Technologies Limited"
    company_currency = frappe.get_cached_value("Company", company, "default_currency") or "NGN"
    default_expense = "403320 - Office Expenses - MTL"
    cache = build_account_cache(company)

    if purchase_id:
        q = f"SELECT * FROM Purchase WHERE Id = '{purchase_id}'"
    else:
        q = "SELECT * FROM Purchase MAXRESULTS 1"

    r = requests.post(endpoint, headers=headers, data=q, timeout=30)
    purchases = r.json().get("QueryResponse", {}).get("Purchase", [])
    if not purchases:
        return {"error": "No Purchase found in QuickBooks."}

    p = purchases[0]
    qb_id = p.get("Id")
    tot_amt = flt(p.get("TotalAmt", 0))
    txn_date = p.get("TxnDate") or nowdate()
    curr = (p.get("CurrencyRef", {}) or {}).get("value") or company_currency
    rate = flt(p.get("ExchangeRate") or 1)
    if rate <= 0:
        rate = 1.0

    bank_ref = p.get("AccountRef", {}) or {}
    bank_account = resolve_bank_account(bank_ref, curr, company)

    entity_ref = p.get("EntityRef", {}) or {}
    entity_type = (entity_ref.get("type") or "Vendor").lower()
    supplier = None
    customer = None
    if entity_type == "customer":
        customer = get_or_create_customer(entity_ref, curr)
    else:
        supplier = get_or_create_supplier(entity_ref, curr)

    accounts = []
    total_debit = 0.0

    lines = p.get("Line", []) or []
    for line in lines:
        amt = flt(line.get("Amount", 0), 2)
        if amt == 0:
            continue

        detail = line.get("AccountBasedExpenseLineDetail") or line.get("ItemBasedExpenseLineDetail") or {}
        acc_ref = detail.get("AccountRef") or detail.get("ItemRef") or {}
        expense_acc = fast_resolve_account(acc_ref, company, default_expense, cache)

        acc_info = cache["raw"].get(expense_acc, {})
        acc_curr = acc_info.get("account_currency") or company_currency
        acc_type = acc_info.get("account_type")

        line_rate = rate
        line_amt = amt
        if acc_curr == "NGN" and curr == "USD":
            line_amt = round(amt * rate, 2)
            line_rate = 1.0
        elif acc_curr == "USD" and curr == "NGN":
            line_amt = round(amt / rate, 2)
            line_rate = rate

        desc = line.get("Description") or p.get("PrivateNote") or f"Direct Expense {qb_id}"

        if line_amt > 0:
            deb_val = line_amt
            crd_val = 0
            total_debit += round(line_amt * line_rate, 2)
        else:
            deb_val = 0
            crd_val = abs(line_amt)
            total_debit -= round(abs(line_amt) * line_rate, 2)

        entry = {
            "account": expense_acc,
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
            entry["party"] = customer or get_or_create_customer(entity_ref, curr)
        elif acc_type == "Payable":
            entry["party_type"] = "Supplier"
            entry["party"] = supplier or get_or_create_supplier(entity_ref, curr)

        accounts.append(entry)

    # Tax Detail if present
    tax_detail = p.get("TxnTaxDetail", {}) or {}
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
            "user_remark": f"VAT Direct Expense {qb_id}",
        })
        total_debit += round(tax_amt * rate, 2)

    # Credit to Bank / Payment Account
    bank_info = cache["raw"].get(bank_account, {})
    bank_curr = bank_info.get("account_currency") or company_currency
    bank_rate = rate
    bank_amt = tot_amt
    if bank_curr == "NGN" and curr == "USD":
        bank_amt = round(tot_amt * rate, 2)
        bank_rate = 1.0

    bank_entry = {
        "account": bank_account,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": round(bank_amt, 2),
        "exchange_rate": bank_rate,
        "cost_center": "QuickBooks - MTL",
        "channel": "QuickBooks",
        "department": "QuickBooks - MTL",
        "user_remark": f"Expense QBO - {qb_id}",
    }
    bank_acc_type = bank_info.get("account_type")
    if bank_acc_type == "Receivable":
        bank_entry["party_type"] = "Customer"
        bank_entry["party"] = customer or get_or_create_customer(None, curr)
    elif bank_acc_type == "Payable":
        bank_entry["party_type"] = "Supplier"
        bank_entry["party"] = supplier or get_or_create_supplier(None, curr)

    accounts.append(bank_entry)

    custom_id = f"EXP-{qb_id}"
    doc_no = p.get("DocNumber")
    ref_no = f"EXP-{doc_no}" if doc_no and len(str(doc_no)) >= 3 else f"EXP-{qb_id}"
    note = p.get("PrivateNote") or f"Direct Expense QBO - {qb_id}"

    existing_je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
    if existing_je:
        je = frappe.get_doc("Journal Entry", existing_je)
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
            "_user_tags": ",QB Expenses,"
        })
        je.flags.ignore_permissions = True
        je.flags.ignore_mandatory = True
        je.flags.ignore_links = True
        je.insert(ignore_permissions=True)
        je.flags.ignore_permissions = True
        je.submit()
        je_name = je.name
        tag_journal_entry(je_name, "QB Expenses")

    frappe.db.commit()

    return {
        "qb_purchase": {
            "id": qb_id,
            "date": txn_date,
            "total_amount": tot_amt,
            "currency": curr,
            "bank_account": bank_ref.get("name"),
            "payee": entity_ref.get("name"),
            "lines": [{"amount": l.get("Amount"), "desc": l.get("Description")} for l in lines]
        },
        "erpnext_journal_entry": {
            "name": je_name,
            "posting_date": txn_date,
            "cheque_no": ref_no,
            "voucher_type": je.voucher_type,
            "docstatus": je.docstatus,
            "total_debit": je.total_debit,
            "total_credit": je.total_credit,
            "accounts": [
                {
                    "account": a.account,
                    "debit": a.debit_in_account_currency,
                    "credit": a.credit_in_account_currency,
                    "party": a.party
                } for a in je.accounts
            ]
        }
    }

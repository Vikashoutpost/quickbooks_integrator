import frappe
import requests
from frappe.utils import getdate, flt
from quickbooks_integration.api.bill_sync import refresh_qb_token
from quickbooks_integration.api.account_mapper import resolve_account_master, build_account_cache

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"
    cache = build_account_cache(company)

    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    query = "SELECT * FROM JournalEntry WHERE TxnDate >= '2023-01-01' AND TxnDate <= '2023-12-31' MAXRESULTS 500"
    url = f"{base_url}/v3/company/{realm_id}/query?query={requests.utils.quote(query)}"
    
    r = requests.get(url, headers=headers)
    data = r.json()
    jes = data.get("QueryResponse", {}).get("JournalEntry", [])
    print(f"Fetched {len(jes)} 2023 Journal Entries from QuickBooks API")

    created = 0
    for je in jes:
        qbo_id = je.get("Id")
        doc_num = je.get("DocNumber")
        txn_date = je.get("TxnDate")
        lines = je.get("Line", [])
        
        # Check if already exists
        existing = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": f"JE-{qbo_id}", "docstatus": 1}, "name")
        if existing:
            continue

        acc_rows = []
        for line in lines:
            detail = line.get("JournalEntryLineDetail", {})
            posting_type = detail.get("PostingType")
            amt = flt(line.get("Amount", 0))
            if not amt:
                continue
            
            acc_ref = detail.get("AccountRef", {})
            acc_name = acc_ref.get("name", "")
            
            # Map account
            mapped_acc = resolve_account_master(acc_name, "", "Movam Technologies Limited", cache)
            if not mapped_acc or mapped_acc not in cache["raw"]:
                # Fallback mapping
                if "interest expense" in acc_name.lower():
                    mapped_acc = "403260 - Interest Expense - MTL"
                elif "foreign exchange" in acc_name.lower():
                    mapped_acc = "403690 - Foreign Exchange Fluctuation - MTL"
                elif "gain on disposal" in acc_name.lower():
                    mapped_acc = "403610 - Gain on Disposal of Assets - MTL"
                elif "interest income" in acc_name.lower():
                    mapped_acc = "403620 - Interest Income - MTL"
                elif "loan payable" in acc_name.lower() or "other payable" in acc_name.lower():
                    mapped_acc = "224040 - Loan Payable - MTL"
                elif "salary advance" in acc_name.lower():
                    mapped_acc = "117020 - Staff Salary Advance - MTL"
                else:
                    mapped_acc = "403320 - Office Expenses - MTL"

            dr = amt if posting_type == "Debit" else 0.0
            cr = amt if posting_type == "Credit" else 0.0
            
            acc_rows.append({
                "account": mapped_acc,
                "debit_in_account_currency": dr,
                "credit_in_account_currency": cr,
                "cost_center": "QuickBooks - MTL",
                "user_remark": line.get("Description") or f"Line for {acc_name}"
            })

        if not acc_rows:
            continue

        tot_dr = sum(r["debit_in_account_currency"] for r in acc_rows)
        tot_cr = sum(r["credit_in_account_currency"] for r in acc_rows)
        if abs(tot_dr - tot_cr) > 0.01:
            diff = tot_dr - tot_cr
            if diff > 0:
                acc_rows.append({
                    "account": "403420 - Round Off - MTL",
                    "debit_in_account_currency": 0.0,
                    "credit_in_account_currency": diff,
                    "cost_center": "QuickBooks - MTL",
                    "user_remark": "Round off balance"
                })
            else:
                acc_rows.append({
                    "account": "403420 - Round Off - MTL",
                    "debit_in_account_currency": -diff,
                    "credit_in_account_currency": 0.0,
                    "cost_center": "QuickBooks - MTL",
                    "user_remark": "Round off balance"
                })

        doc = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": company,
            "posting_date": getdate(txn_date),
            "custom_quickbooks_je_id": f"JE-{qbo_id}",
            "user_remark": f"QuickBooks JE {doc_num or qbo_id}",
            "accounts": acc_rows
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True)
        doc.submit()
        created += 1

    frappe.db.commit()
    print(f"Created and posted {created} 2023 Journal Entries!")


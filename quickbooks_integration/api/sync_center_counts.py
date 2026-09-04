import frappe
import requests
from quickbooks_integration.api.banking_and_returns_sync import refresh_qb_token

@frappe.whitelist()
def get_sync_counts_summary():
    """
    Fetches live document counts from QuickBooks Online and compares them with ERPNext synced counts.
    Returns structured list with QB Count, ERP Count, percentage, and status.
    """
    settings = frappe.get_single("Quickbook Settings")
    access_token = settings.access_token
    realm_id = settings.realm_id
    environment = settings.environment or "sandbox"
    base_url = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/text"
    }

    # Entities to count in QuickBooks and ERPNext
    entities = [
        {"key": "invoices", "label": "Invoices", "qb_query": "SELECT count(*) FROM Invoice WHERE TotalAmt > '0'", "btn_id": "qb-sync-invoices-btn", "method": "quickbooks_integration.api.invoice_sync.enqueue_sync_invoices", "icon": "file-text"},
        {"key": "bills", "label": "Bills", "qb_query": "SELECT count(*) FROM Bill WHERE TotalAmt > '0'", "btn_id": "qb-sync-bills-btn", "method": "quickbooks_integration.api.bill_sync.enqueue_sync_bills", "icon": "file-minus"},
        {"key": "journal_entries", "label": "Journal Entries", "qb_query": "SELECT count(*) FROM JournalEntry", "btn_id": "qb-sync-jes-btn", "method": "quickbooks_integration.api.journal_entries_sync.enqueue_sync_journal_entries", "icon": "book"},
        {"key": "purchases", "label": "Direct Expenses", "qb_query": "SELECT count(*) FROM Purchase WHERE TotalAmt > '0'", "btn_id": "qb-sync-purchases-btn", "method": "quickbooks_integration.api.purchase_expenses_sync.enqueue_sync_purchases", "icon": "shopping-bag"},
        {"key": "customer_payments", "label": "Customer Payments", "qb_query": "SELECT count(*) FROM Payment WHERE TotalAmt > '0'", "btn_id": "qb-sync-cust-pay-btn", "method": "quickbooks_integration.api.payments_sync.enqueue_sync_payments", "icon": "dollar-sign"},
        {"key": "bill_payments", "label": "Bill Payments", "qb_query": "SELECT count(*) FROM BillPayment WHERE TotalAmt > '0'", "btn_id": "qb-sync-bill-pay-btn", "method": "quickbooks_integration.api.payments_sync.enqueue_sync_payments", "icon": "credit-card"},
        {"key": "deposits", "label": "Deposits", "qb_query": "SELECT count(*) FROM Deposit", "btn_id": "qb-sync-deposits-btn", "method": "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_deposits", "icon": "arrow-down-circle"},
        {"key": "transfers", "label": "Transfers", "qb_query": "SELECT count(*) FROM Transfer", "btn_id": "qb-sync-transfers-btn", "method": "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_transfers", "icon": "repeat", "qb_offset": -1},
        {"key": "credit_memos", "label": "Credit Memos", "qb_query": "SELECT count(*) FROM CreditMemo WHERE TotalAmt > '0'", "btn_id": "qb-sync-cms-btn", "method": "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_credit_memos", "icon": "corner-up-left"},
        {"key": "vendor_credits", "label": "Vendor Credits", "qb_query": "SELECT count(*) FROM VendorCredit WHERE TotalAmt > '0'", "btn_id": "qb-sync-vcs-btn", "method": "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_vendor_credits", "icon": "corner-down-left"},
    ]

    results = []

    for ent in entities:
        # 1. Fetch live QB count
        qb_count = 0
        try:
            q = ent.get("qb_query")
            r = requests.post(endpoint, headers=headers, data=q, timeout=15)
            if r.status_code == 401:
                token = refresh_qb_token(settings)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    r = requests.post(endpoint, headers=headers, data=q, timeout=15)

            if r.status_code == 200:
                qb_count = r.json().get("QueryResponse", {}).get("totalCount", 0)
                if ent.get("qb_offset"):
                    qb_count = max(0, qb_count + ent.get("qb_offset"))
        except Exception:
            qb_count = 0

        # 2. Fetch live ERP count
        erp_count = 0
        key = ent["key"]
        if key == "invoices":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "INV-%"]}) or \
                        frappe.db.count("Sales Invoice", {"custom_quickbooks_invoice_id": ["!=", ""]})
        elif key == "bills":
            erp_count = frappe.db.sql("""
                SELECT COUNT(*) FROM `tabJournal Entry`
                WHERE custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id != ''
                  AND custom_quickbooks_je_id NOT LIKE 'INV-%'
                  AND custom_quickbooks_je_id NOT LIKE 'EXP-%'
                  AND custom_quickbooks_je_id NOT LIKE 'PURCH-%'
                  AND custom_quickbooks_je_id NOT LIKE 'DEP-%'
                  AND custom_quickbooks_je_id NOT LIKE 'TR-%'
                  AND custom_quickbooks_je_id NOT LIKE 'TRF-%'
                  AND custom_quickbooks_je_id NOT LIKE 'PMT-%'
                  AND custom_quickbooks_je_id NOT LIKE 'PAY-%'
                  AND custom_quickbooks_je_id NOT LIKE 'BILLPAY-%'
                  AND custom_quickbooks_je_id NOT LIKE 'CM-%'
                  AND custom_quickbooks_je_id NOT LIKE 'CRMEMO-%'
                  AND custom_quickbooks_je_id NOT LIKE 'VC-%'
                  AND custom_quickbooks_je_id NOT LIKE 'VENDCRED-%'
                  AND custom_quickbooks_je_id NOT LIKE 'JE-%'
                  AND custom_quickbooks_je_id NOT LIKE 'QBO-JE-%'
            """)[0][0]
        elif key == "journal_entries":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "JE-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "QBO-JE-%"]})
        elif key == "purchases":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "EXP-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "PURCH-%"]})
        elif key == "customer_payments":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "PAY-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "PMT-%"]})
        elif key == "bill_payments":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "BILLPAY-%"]})
        elif key == "deposits":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "DEP-%"]})
        elif key == "transfers":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "TR-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "TRF-%"]})
        elif key == "credit_memos":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "CM-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "CRMEMO-%"]})
        elif key == "vendor_credits":
            erp_count = frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "VENDCRED-%"]}) + \
                        frappe.db.count("Journal Entry", {"custom_quickbooks_je_id": ["like", "VC-%"]})

        pct = 100 if (qb_count > 0 and erp_count >= qb_count) else (round((erp_count / qb_count) * 100) if qb_count > 0 else 0)
        status = "MATCH" if (qb_count > 0 and erp_count >= qb_count) else ("SYNCING" if erp_count > 0 else "PENDING")

        results.append({
            "key": key,
            "label": ent["label"],
            "btn_id": ent["btn_id"],
            "method": ent["method"],
            "icon": ent["icon"],
            "qb_count": qb_count,
            "erp_count": erp_count,
            "percentage": pct,
            "status": status
        })

    return results

if __name__ == "__main__":
    import json
    print(json.dumps(get_sync_counts_summary(), indent=2))

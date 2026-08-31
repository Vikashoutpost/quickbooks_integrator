import frappe
import requests
from frappe.utils import flt
from quickbooks_integration.api.bill_sync import refresh_qb_token

def run():
    frappe.flags.in_import = True
    settings = frappe.get_single("Quickbook Settings")
    token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if (settings.environment or "sandbox") == "sandbox" else "https://quickbooks.api.intuit.com"
    endpoint = f"{base_url}/v3/company/{realm_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/text"}

    # 1. Check all 2022 Payments
    q = "SELECT Id, TotalAmt, DocNumber FROM Payment WHERE TxnDate >= '2022-01-01' AND TxnDate <= '2022-12-31' MAXRESULTS 1000"
    r = requests.post(endpoint, headers=headers, data=q)
    payments = r.json().get("QueryResponse", {}).get("Payment", [])
    
    deleted_p = 0
    for p in payments:
        tot = flt(p.get("TotalAmt", 0))
        pid = p.get("Id")
        if tot <= 0:
            custom_id = f"PAY-{pid}"
            je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if je:
                print(f"Cancelling zero payment {custom_id} -> {je}")
                doc = frappe.get_doc("Journal Entry", je)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete()
                deleted_p += 1

    # 2. Check all 2022 BillPayments
    q_bp = "SELECT Id, TotalAmt, DocNumber FROM BillPayment WHERE TxnDate >= '2022-01-01' AND TxnDate <= '2022-12-31' MAXRESULTS 1000"
    r_bp = requests.post(endpoint, headers=headers, data=q_bp)
    bill_payments = r_bp.json().get("QueryResponse", {}).get("BillPayment", [])

    deleted_bp = 0
    for bp in bill_payments:
        tot = flt(bp.get("TotalAmt", 0))
        bpid = bp.get("Id")
        if tot <= 0:
            custom_id = f"BILLPAY-{bpid}"
            je = frappe.db.get_value("Journal Entry", {"custom_quickbooks_je_id": custom_id}, "name")
            if je:
                print(f"Cancelling zero bill payment {custom_id} -> {je}")
                doc = frappe.get_doc("Journal Entry", je)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete()
                deleted_bp += 1

    frappe.db.commit()
    print(f"Done cleaning: {deleted_p} zero Payments deleted, {deleted_bp} zero BillPayments deleted.")


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

    # 1. Fetch ALL zero Payments from QBO
    start_position = 1
    max_results = 1000
    zero_payment_ids = []

    while True:
        q = f"SELECT Id, TotalAmt, DocNumber FROM Payment STARTPOSITION {start_position} MAXRESULTS {max_results}"
        r = requests.post(endpoint, headers=headers, data=q)
        if r.status_code == 401:
            token = refresh_qb_token(settings)
            headers["Authorization"] = f"Bearer {token}"
            r = requests.post(endpoint, headers=headers, data=q)
        
        batch = r.json().get("QueryResponse", {}).get("Payment", [])
        if not batch:
            break
        for p in batch:
            if flt(p.get("TotalAmt", 0)) <= 0:
                zero_payment_ids.append(str(p.get("Id")))
        if len(batch) < max_results:
            break
        start_position += max_results

    print(f"Total zero-amount Payments in QBO: {len(zero_payment_ids)}")

    # 2. Fetch ALL zero BillPayments from QBO
    start_position = 1
    zero_bill_payment_ids = []

    while True:
        q = f"SELECT Id, TotalAmt, DocNumber FROM BillPayment STARTPOSITION {start_position} MAXRESULTS {max_results}"
        r = requests.post(endpoint, headers=headers, data=q)
        if r.status_code == 401:
            token = refresh_qb_token(settings)
            headers["Authorization"] = f"Bearer {token}"
            r = requests.post(endpoint, headers=headers, data=q)
        
        batch = r.json().get("QueryResponse", {}).get("BillPayment", [])
        if not batch:
            break
        for bp in batch:
            if flt(bp.get("TotalAmt", 0)) <= 0:
                zero_bill_payment_ids.append(str(bp.get("Id")))
        if len(batch) < max_results:
            break
        start_position += max_results

    print(f"Total zero-amount BillPayments in QBO: {len(zero_bill_payment_ids)}")

    # 3. Clean zero Payments from ERPNext via SQL
    custom_pay_ids = [f"PAY-{pid}" for pid in zero_payment_ids]
    if custom_pay_ids:
        # Get matching JE names
        jes_pay = frappe.db.sql("""
            SELECT name FROM `tabJournal Entry`
            WHERE custom_quickbooks_je_id IN %s
        """, (tuple(custom_pay_ids),), as_dict=True)
        pay_names = [j["name"] for j in jes_pay]
        if pay_names:
            print(f"Deleting {len(pay_names)} zero Payment JVs...")
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no IN %s", (tuple(pay_names),))
            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no IN %s", (tuple(pay_names),))
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent IN %s", (tuple(pay_names),))
            frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name IN %s", (tuple(pay_names),))

    # 4. Clean zero BillPayments from ERPNext via SQL
    custom_bp_ids = [f"BILLPAY-{bpid}" for bpid in zero_bill_payment_ids]
    if custom_bp_ids:
        jes_bp = frappe.db.sql("""
            SELECT name FROM `tabJournal Entry`
            WHERE custom_quickbooks_je_id IN %s
        """, (tuple(custom_bp_ids),), as_dict=True)
        bp_names = [j["name"] for j in jes_bp]
        if bp_names:
            print(f"Deleting {len(bp_names)} zero BillPayment JVs...")
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no IN %s", (tuple(bp_names),))
            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no IN %s", (tuple(bp_names),))
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent IN %s", (tuple(bp_names),))
            frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name IN %s", (tuple(bp_names),))

    frappe.db.commit()
    print("Zero-dollar payment cleanup completed successfully!")


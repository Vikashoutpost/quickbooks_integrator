import frappe
import json
import hmac
import hashlib
import base64

@frappe.whitelist(allow_guest=True)
def handle_qbo_webhook():
    try:
        raw = frappe.local.request.get_data(as_text=True)
        headers = dict(frappe.local.request.headers or {})

        # Parse body safely
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {}

        # Handle verification challenge
        if isinstance(body, dict) and "challenge" in body:
            frappe.local.response.update({
                "http_status_code": 200,
                "type": "application/json",
                "message": json.dumps({"challenge": body["challenge"]})
            })
            return frappe.local.response["message"]

        # Verify signature
        signature = headers.get("intuit-signature")
        client_secret = frappe.get_single("Quickbook Settings").client_secret or ""
        if not _verify_signature(raw, signature, client_secret):
            frappe.local.response.update({
                "http_status_code": 401,
                "message": "Invalid signature"
            })
            return "Invalid signature"

        # Process event notifications
        for note in body.get("eventNotifications", []):
            for ent in note.get("dataChangeEvent", {}).get("entities", []):
                entity_type = ent.get("name")  # e.g. Customer, Invoice
                entity_id = ent.get("id")
                operation = ent.get("operation", "Update")

                frappe.enqueue(
                    "quickbooks_integration.api.webhooks.process_qbo_event",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    operation=operation,
                )

        frappe.local.response.update({
            "http_status_code": 200,
            "message": "OK"
        })
        return "OK"

    except Exception:
        frappe.log_error(frappe.get_traceback(), "QuickBooks Webhook Error")
        frappe.local.response.update({
            "http_status_code": 500,
            "message": "Error"
        })
        return "Error"


def _verify_signature(payload_text, signature, client_secret):
    """Verify HMAC-SHA256 signature from QuickBooks"""
    if not signature or not client_secret:
        return False
    digest = hmac.new(
        client_secret.encode("utf-8"),
        payload_text.encode("utf-8"),
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(signature, expected)


@frappe.whitelist()
def process_qbo_event(entity_type, entity_id, operation="Update"):
    """
    Route QuickBooks webhook events to the correct sync function.
    """
    mapping = {
        "Customer": "quickbooks_integration.api.customer_sync.sync_customer",
        "Vendor": "quickbooks_integration.api.vendor_sync.sync_vendor",
        "Invoice": "quickbooks_integration.api.invoice_sync.sync_invoice",
        "Bill": "quickbooks_integration.api.bill_sync.sync_bill",
        "Payment": "quickbooks_integration.api.payment_sync.sync_payment",
        "JournalEntry": "quickbooks_integration.api.journal_entries_sync.sync_journal_entry",
    }

    func = mapping.get(entity_type)
    if func:
        frappe.enqueue(func, qbo_id=entity_id, operation=operation)

import frappe
from frappe.utils import nowdate, flt
import time

def run_full_sync(user=None):
    """
    Automated end-to-end QuickBooks full sync pipeline.
    Executes all sync steps sequentially, ensuring complete GL consistency,
    automatic inventory valuation, and auto-tagging.
    """
    start_time = time.time()
    frappe.logger("quickbooks_sync").info("Starting automated full QuickBooks synchronization...")

    def update_progress(pct, title, desc):
        if user:
            try:
                frappe.publish_progress(percent=pct, title=title, description=desc, user=user)
            except Exception:
                pass

    try:
        # Step 0: Token Refresh & Defaults
        update_progress(5, "QuickBooks Full Sync", "Refreshing OAuth tokens & configuring defaults...")
        from quickbooks_integration.api.bill_sync import refresh_qb_token
        settings = frappe.get_single("Quickbook Settings")
        token = refresh_qb_token(settings)

        company = frappe.defaults.get_global_default("company") or "Movan Technologies Limited"
        frappe.db.set_value("Company", company, {
            "default_receivable_account": "121010 - Trade Receivables - NGN - MTL",
            "default_payable_account": "225010 - Trade Creditors - NGN - MTL",
            "default_expense_account": "403320 - Office Expenses - MTL",
            "default_income_account": "311010 - Revenue - SAAS - MTL"
        })
        frappe.db.commit()

        # Step 1: Masters (Customers, Vendors, Items, Accounts)
        update_progress(15, "Syncing Master Data", "Fetching customers, vendors, items and accounts...")
        try:
            from quickbooks_integration.api.customer_sync import sync_quickbooks_customers
            sync_quickbooks_customers()
        except Exception as e:
            frappe.log_error(f"Sync Customers Error: {e}", "QuickBooks Sync")

        try:
            from quickbooks_integration.api.vendor_sync import sync_quickbooks_vendors
            sync_quickbooks_vendors()
        except Exception as e:
            frappe.log_error(f"Sync Vendors Error: {e}", "QuickBooks Sync")

        try:
            from quickbooks_integration.api.item_sync import sync_quickbooks_items
            sync_quickbooks_items()
        except Exception as e:
            frappe.log_error(f"Sync Items Error: {e}", "QuickBooks Sync")

        try:
            from quickbooks_integration.api.account_sync import sync_quickbooks_accounts
            sync_quickbooks_accounts()
        except Exception as e:
            frappe.log_error(f"Sync Accounts Error: {e}", "QuickBooks Sync")

        # Step 2: Sales Invoices
        update_progress(30, "Syncing Sales", "Fetching and reconciling sales invoices...")
        try:
            from quickbooks_integration.api.invoice_sync import sync_quickbooks_invoices
            sync_quickbooks_invoices()
        except Exception as e:
            frappe.log_error(f"Sync Invoices Error: {e}", "QuickBooks Sync")

        # Step 3: Bills & Vendor Invoices
        update_progress(45, "Syncing Bills", "Fetching vendor bills and expenses...")
        try:
            from quickbooks_integration.api.bill_sync import sync_quickbooks_bills
            sync_quickbooks_bills()
        except Exception as e:
            frappe.log_error(f"Sync Bills Error: {e}", "QuickBooks Sync")

        # Step 4: Direct Expenses / Purchases
        update_progress(60, "Syncing Direct Expenses", "Fetching direct cash and bank expenses...")
        try:
            from quickbooks_integration.api.purchase_expenses_sync import sync_quickbooks_purchases
            sync_quickbooks_purchases()
        except Exception as e:
            frappe.log_error(f"Sync Purchases Error: {e}", "QuickBooks Sync")

        # Step 5: General Journal Entries
        update_progress(75, "Syncing Journal Entries", "Fetching adjustments and legacy journals...")
        try:
            from quickbooks_integration.api.journal_entries_sync import sync_quickbooks_journal_entries
            sync_quickbooks_journal_entries()
        except Exception as e:
            frappe.log_error(f"Sync Journals Error: {e}", "QuickBooks Sync")

        # Step 6: Banking (Payments, Transfers, Deposits, Credit Memos)
        update_progress(85, "Syncing Banking & Payments", "Fetching payments, deposits and transfers...")
        try:
            from quickbooks_integration.api.payments_sync import sync_quickbooks_payments
            sync_quickbooks_payments()
        except Exception as e:
            frappe.log_error(f"Sync Payments Error: {e}", "QuickBooks Sync")

        try:
            from quickbooks_integration.api.banking_and_returns_sync import (
                sync_quickbooks_transfers,
                sync_quickbooks_deposits,
                sync_quickbooks_credit_memos,
                sync_quickbooks_vendor_credits
            )
            sync_quickbooks_transfers()
            sync_quickbooks_deposits()
            sync_quickbooks_credit_memos()
            sync_quickbooks_vendor_credits()
        except Exception as e:
            frappe.log_error(f"Sync Banking Error: {e}", "QuickBooks Sync")

        # Step 7: Automated Inventory & Multi-Currency Valuation Alignment
        update_progress(95, "Aligning Valuation & Currencies", "Computing inventory valuation and FX adjustments...")
        try:
            from quickbooks_integration.api.inventory_cogs_sync import sync_inventory_cogs_valuation
            sync_inventory_cogs_valuation(company=company)
        except Exception as e:
            frappe.log_error(f"Sync Inventory Valuation Error: {e}", "QuickBooks Sync")

        # Step 8: Bulk Auto-Tagging
        update_progress(98, "Finalizing Sync", "Auto-tagging all entries for live ledger reconciliation...")
        try:
            from quickbooks_integration.fast_bulk_tag import run as bulk_tag_run
            bulk_tag_run()
        except Exception as e:
            frappe.log_error(f"Bulk Tagging Error: {e}", "QuickBooks Sync")

        update_progress(100, "Sync Complete", "QuickBooks synchronization completed successfully.")
        elapsed = round(time.time() - start_time, 2)
        msg = f"Full QuickBooks sync completed successfully in {elapsed}s."
        if user:
            frappe.publish_realtime("msgprint", msg, user=user)
        return msg

    except Exception as e:
        err_msg = f"QuickBooks full sync failed: {str(e)}"
        frappe.log_error(err_msg, "QuickBooks Full Sync")
        if user:
            frappe.publish_realtime("msgprint", f"❌ {err_msg}", user=user)
        return err_msg


@frappe.whitelist()
def enqueue_sync_all():
    """
    Whitelisted entry point from UI to trigger full automated background synchronization.
    """
    user = frappe.session.user
    frappe.enqueue(
        "quickbooks_integration.api.sync_all.run_full_sync",
        queue="long",
        timeout=3600,
        user=user
    )
    return "Full QuickBooks synchronization started in background. Both Trial Balance and Balance Sheet will automatically align upon completion."

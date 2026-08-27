// Copyright (c) 2025, maddy and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quickbook Settings", {
    refresh(frm) {
        frm.clear_custom_buttons();

        // 1. Primary Action: Connect QuickBooks
        frm.add_custom_button(__("Connect QuickBooks"), function () {
            frappe.call({
                method: "quickbooks_integration.api.oauth.get_auth_url",
                callback: function (r) {
                    if (r.message) {
                        window.open(r.message, "_blank");
                    } else {
                        frappe.msgprint(__("Failed to generate authorization URL."));
                    }
                }
            });
        }).addClass("btn-primary");

        // 2. Grouped Dropdown: Accounting & Transactions Sync
        frm.add_custom_button(__("Fetch Bills"), function () {
            frappe.call({
                method: "quickbooks_integration.api.bill_sync.enqueue_sync_bills",
                callback: function (r) {
                    frappe.show_alert({
                        message: r.message || __("Bill sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Invoices"), function () {
            frappe.call({
                method: "quickbooks_integration.api.invoice_sync.enqueue_sync_invoices",
                callback: function (r) {
                    frappe.show_alert({
                        message: r.message || __("Invoice sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Journal Entries"), function() {
            frappe.call({
                method: "quickbooks_integration.api.journal_entries_sync.enqueue_sync_journal_entries",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Journal Entries sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Payments"), function() {
            frappe.call({
                method: "quickbooks_integration.api.payments_sync.enqueue_sync_payments",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Payments sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Stop / Cancel Sync"), function() {
            frappe.confirm(__("Are you sure you want to stop any currently running background sync?"), function() {
                frappe.call({
                    method: "quickbooks_integration.api.journal_entries_sync.cancel_sync",
                    callback: function(r) {
                        frappe.show_alert({
                            message: r.message || __("Sync stop signal sent."),
                            indicator: "orange"
                        }, 8);
                    }
                });
            });
        }, __("Sync Transactions"));

        // 3. Grouped Dropdown: Master Data Sync
        frm.add_custom_button(__("Fetch Customers"), function () {
            frappe.call({
                method: "quickbooks_integration.api.customer_sync.sync_quickbooks_customers",
                freeze: true,
                freeze_message: __("Syncing Customers..."),
                callback: function (r) {
                    frappe.msgprint(r.message || __("Customers synced successfully."));
                }
            });
        }, __("Master Data"));

        frm.add_custom_button(__("Fetch Vendors"), function () {
            frappe.call({
                method: "quickbooks_integration.api.vendor_sync.sync_quickbooks_vendors",
                freeze: true,
                freeze_message: __("Syncing Vendors..."),
                callback: function (r) {
                    frappe.msgprint(r.message || __("Vendors synced successfully."));
                }
            });
        }, __("Master Data"));

        frm.add_custom_button(__("Fetch Items"), function () {
            frappe.call({
                method: "quickbooks_integration.api.item_sync.sync_quickbooks_items",
                freeze: true,
                freeze_message: __("Syncing Items..."),
                callback: function (r) {
                    frappe.msgprint(r.message || __("Items synced."));
                }
            });
        }, __("Master Data"));

        frm.add_custom_button(__("Fetch Accounts"), function () {
            frappe.call({
                method: "quickbooks_integration.api.account_sync.sync_quickbooks_chart_of_accounts",
                freeze: true,
                freeze_message: __("Syncing Chart of Accounts..."),
                callback: function (r) {
                    frappe.msgprint(r.message || __("Accounts synced."));
                }
            });
        }, __("Master Data"));

        frm.add_custom_button(__("Fetch Employees"), function () {
            frappe.call({
                method: "quickbooks_integration.api.employee_sync.sync_quickbooks_employees",
                freeze: true,
                freeze_message: __("Syncing Employees..."),
                callback: function (r) {
                    frappe.msgprint(r.message || __("Employees synced."));
                }
            });
        }, __("Master Data"));

        frm.add_custom_button(__("Fetch Company Info"), function () {
            frappe.call({
                method: "quickbooks_integration.api.comapany_info.get_quickbooks_company_info",
                freeze: true,
                freeze_message: __("Fetching Company Info..."),
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(__("Company Info: ") + JSON.stringify(r.message, null, 2));
                    }
                }
            });
        }, __("Master Data"));

        // 4. Render In-Form Quick Actions Panel
        render_sync_dashboard(frm);
    }
});

function render_sync_dashboard(frm) {
    if (frm.dashboard_rendered) return;
    frm.dashboard_rendered = true;

    const isConnected = !!frm.doc.access_token;
    const env = frm.doc.environment || "sandbox";

    const dashboard_html = `
        <div class="qb-dashboard" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                <div>
                    <h4 style="margin: 0; font-size: 15px; font-weight: 600; color: #1e293b;">QuickBooks Sync Center</h4>
                    <span style="font-size: 12px; color: #64748b;">Environment: <strong>${env.toUpperCase()}</strong> | Status: <span style="color: ${isConnected ? '#16a34a' : '#dc2626'}; font-weight: 600;">${isConnected ? 'Connected' : 'Not Connected'}</span></span>
                </div>
                <button class="btn btn-default btn-xs" id="qb-cancel-sync-btn" style="color: #dc2626; border-color: #fca5a5;">
                    Stop / Cancel Sync
                </button>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px;">
                <button class="btn btn-default btn-sm" id="qb-sync-bills-btn" style="text-align: left; padding: 10px 12px;">
                    <div style="font-weight: 600; color: #0f172a;">Fetch Bills</div>
                    <div style="font-size: 11px; color: #64748b;">Tag: QB Bills</div>
                </button>
                <button class="btn btn-default btn-sm" id="qb-sync-invoices-btn" style="text-align: left; padding: 10px 12px;">
                    <div style="font-weight: 600; color: #0f172a;">Fetch Invoices</div>
                    <div style="font-size: 11px; color: #64748b;">Tag: QB Sales</div>
                </button>
                <button class="btn btn-default btn-sm" id="qb-sync-jes-btn" style="text-align: left; padding: 10px 12px;">
                    <div style="font-weight: 600; color: #0f172a;">Fetch Journal Entries</div>
                    <div style="font-size: 11px; color: #64748b;">Tag: QB Journals</div>
                </button>
                <button class="btn btn-default btn-sm" id="qb-sync-payments-btn" style="text-align: left; padding: 10px 12px;">
                    <div style="font-weight: 600; color: #0f172a;">Fetch Payments</div>
                    <div style="font-size: 11px; color: #64748b;">Tag: QB Payments</div>
                </button>
            </div>
        </div>
    `;

    frm.dashboard.set_headline(dashboard_html);

    // Bind In-Form Dashboard Click Handlers
    setTimeout(() => {
        frm.page.main.find("#qb-sync-bills-btn").on("click", function() {
            frappe.call({
                method: "quickbooks_integration.api.bill_sync.enqueue_sync_bills",
                callback: function(r) {
                    frappe.show_alert({ message: r.message || __("Bill sync started in background..."), indicator: "blue" }, 8);
                }
            });
        });

        frm.page.main.find("#qb-sync-invoices-btn").on("click", function() {
            frappe.call({
                method: "quickbooks_integration.api.invoice_sync.enqueue_sync_invoices",
                callback: function(r) {
                    frappe.show_alert({ message: r.message || __("Invoice sync started in background..."), indicator: "blue" }, 8);
                }
            });
        });

        frm.page.main.find("#qb-sync-jes-btn").on("click", function() {
            frappe.call({
                method: "quickbooks_integration.api.journal_entries_sync.enqueue_sync_journal_entries",
                callback: function(r) {
                    frappe.show_alert({ message: r.message || __("Journal Entries sync started in background..."), indicator: "blue" }, 8);
                }
            });
        });

        frm.page.main.find("#qb-sync-payments-btn").on("click", function() {
            frappe.call({
                method: "quickbooks_integration.api.payments_sync.enqueue_sync_payments",
                callback: function(r) {
                    frappe.show_alert({ message: r.message || __("Payments sync started in background..."), indicator: "blue" }, 8);
                }
            });
        });

        frm.page.main.find("#qb-cancel-sync-btn").on("click", function() {
            frappe.confirm(__("Are you sure you want to stop any currently running background sync?"), function() {
                frappe.call({
                    method: "quickbooks_integration.api.journal_entries_sync.cancel_sync",
                    callback: function(r) {
                        frappe.show_alert({ message: r.message || __("Sync stop signal sent."), indicator: "orange" }, 8);
                    }
                });
            });
        });
    }, 300);
}

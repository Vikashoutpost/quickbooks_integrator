// Copyright (c) 2025, maddy and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quickbook Settings", {
    refresh(frm) {
        frm.add_custom_button("Connect QuickBooks", function () {
            frappe.call({
                method: "quickbooks_integration.api.oauth.get_auth_url",
                callback: function (r) {
                    if (r.message) {
                        window.open(r.message, "_blank");
                    } else {
                        frappe.msgprint("Failed to generate authorization URL.");
                    }
                }
            });
        });
        frm.add_custom_button("Fetch Customers", function () {
            frappe.call({
                method: "quickbooks_integration.api.customer_sync.sync_quickbooks_customers",
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    } else {
                        frappe.msgprint("Failed to sync customers.");
                    }
                }
            });
        });
        frm.add_custom_button("Fetch Vendors", function () {
            frappe.call({
                method: "quickbooks_integration.api.vendor_sync.sync_quickbooks_vendors",
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    } else {
                        frappe.msgprint("Failed to sync vendors.");
                    }
                }
            });
        });
        frm.add_custom_button("Fetch Items", function () {
            frappe.call({
                method: "quickbooks_integration.api.item_sync.sync_quickbooks_items",
                callback: function (r) {
                    frappe.msgprint(r.message || "Failed to sync items.");
                }
            });
        });
        frm.add_custom_button("Fetch Accounts", function () {
            frappe.call({
                method: "quickbooks_integration.api.account_sync.sync_quickbooks_chart_of_accounts",
                callback: function (r) {
                    frappe.msgprint(r.message || "Failed to sync accounts.");
                }
            });
        });
        frm.add_custom_button("Fetch Invoices", function () {
            frappe.call({
                method: "quickbooks_integration.api.invoice_sync.sync_quickbooks_invoices",
                callback: function (r) {
                    frappe.msgprint(r.message || "Failed to sync invoices.");
                }
            });
        });
        frm.add_custom_button("Fetch Bills", function () {
            frappe.call({
                method: "quickbooks_integration.api.bill_sync.sync_quickbooks_bills",
                callback: function (r) {
                    frappe.msgprint(r.message || "Failed to sync bills.");
                }
            });
        });
        frm.add_custom_button(__('Fetch Payments'), function() {
            frappe.call({
                method: "quickbooks_integration.api.payments_sync.sync_quickbooks_payments",
                callback: function(r) {
                    frappe.msgprint(r.message || "Payments synced successfully.");
                }
            });
        });
        frm.add_custom_button("Fetch Journal Entries", function() {
            frappe.call({
                method: "quickbooks_integration.api.journal_entries_sync.sync_quickbooks_journal_entries",
                callback: function(r) {
                    if (!r.exc) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        });
        frm.add_custom_button("Fetch Employees", function () {
            frappe.call({
                method: "quickbooks_integration.api.employee_sync.sync_quickbooks_employees",
                callback: function (r) {
                    frappe.msgprint(r.message || "Failed to sync employees.");
                }
            });
        });
        frm.add_custom_button("Fetch Company Info", function () {
            frappe.call({
                method: "quickbooks_integration.api.comapany_info.get_quickbooks_company_info",
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint("Company Info: " + JSON.stringify(r.message, null, 2));
                    } else {
                        frappe.msgprint("Failed to fetch company info.");
                    }
                }
            });
        });
    }
});


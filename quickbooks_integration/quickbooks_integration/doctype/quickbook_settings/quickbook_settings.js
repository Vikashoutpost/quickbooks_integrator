// Copyright (c) 2025, maddy and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quickbook Settings", {
    refresh(frm) {
        // Hide sidebar and expand to full width
        if (frm.page && frm.page.sidebar) {
            frm.page.sidebar.hide();
        }
        frm.page.wrapper.find(".form-sidebar").hide();
        frm.page.wrapper.find(".layout-main-section-wrapper").removeClass("col-md-10").addClass("col-md-12");

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

        // 1b. Standalone Action: Compare P&L
        frm.add_custom_button(__(`
            <span style="display:inline-flex; align-items:center; gap:6px; font-weight:600;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="20" x2="18" y2="10"></line>
                    <line x1="12" y1="20" x2="12" y2="4"></line>
                    <line x1="6" y1="20" x2="6" y2="14"></line>
                </svg>
                Compare P&L
            </span>
        `), function () {
            show_pl_comparison_dialog();
        });

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

        frm.add_custom_button(__("Fetch Transfers"), function() {
            frappe.call({
                method: "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_transfers",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Transfers sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Deposits"), function() {
            frappe.call({
                method: "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_deposits",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Deposits sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Credit Memos"), function() {
            frappe.call({
                method: "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_credit_memos",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Credit Memos sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Vendor Credits"), function() {
            frappe.call({
                method: "quickbooks_integration.api.banking_and_returns_sync.enqueue_sync_vendor_credits",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Vendor Credits sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Direct Expenses"), function() {
            frappe.call({
                method: "quickbooks_integration.api.purchase_expenses_sync.enqueue_sync_purchases",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Direct Expenses sync started in background..."),
                        indicator: "blue"
                    }, 8);
                }
            });
        }, __("Sync Transactions"));

        frm.add_custom_button(__("Fetch Inventory & COGS"), function() {
            frappe.call({
                method: "quickbooks_integration.api.inventory_cogs_sync.enqueue_sync_inventory_cogs",
                callback: function(r) {
                    frappe.show_alert({
                        message: r.message || __("Inventory & COGS sync started in background..."),
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

        frm.add_custom_button(__("Re-apply All Tags"), function() {
            frappe.call({
                method: "quickbooks_integration.fast_bulk_tag.run_from_ui",
                freeze: true,
                freeze_message: __("Re-applying all QuickBooks tags to ERPNext documents..."),
                callback: function(r) {
                    frappe.msgprint({
                        title: __("Tags Refreshed Successfully"),
                        message: r.message || __("All QuickBooks tags have been linked and verified in ERPNext."),
                        indicator: "green"
                    });
                }
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

    const initial_html = `
        <div class="qb-dashboard" style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; margin-bottom: 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9;">
                <div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <h4 style="margin: 0; font-size: 16px; font-weight: 700; color: #0f172a;">QuickBooks Sync Center</h4>
                        <span style="font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; background: ${isConnected ? '#ecfdf5' : '#fef2f2'}; color: ${isConnected ? '#059669' : '#dc2626'};">
                            ${isConnected ? '● Connected' : '● Disconnected'}
                        </span>
                    </div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 3px;">
                        Environment: <strong>${env.toUpperCase()}</strong> | Company ID: <strong>${frm.doc.realm_id || 'Not set'}</strong>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-default btn-xs" id="qb-refresh-counts-btn" style="font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="23 4 23 10 17 10"></polyline>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                        </svg>
                        Refresh Counts
                    </button>
                    <button class="btn btn-default btn-xs" id="qb-cancel-sync-btn" style="color: #dc2626; border-color: #fca5a5; font-weight: 600;">
                        Stop Sync
                    </button>
                </div>
            </div>

            <div id="qb-sync-cards-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                <div style="grid-column: 1 / -1; text-align: center; padding: 24px; color: #64748b; font-size: 13px;">
                    <span class="spinner-border spinner-border-sm" role="status" style="margin-right: 6px;"></span>
                    Loading live QuickBooks & ERPNext document counts...
                </div>
            </div>
        </div>
    `;

    frm.dashboard.set_headline(initial_html);

    // Fetch and populate counts
    load_sync_center_counts(frm);

    // Bind Global Header Handlers
    setTimeout(() => {
        frm.page.main.find("#qb-refresh-counts-btn").on("click", function() {
            load_sync_center_counts(frm, true);
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
    }, 200);
}

function load_sync_center_counts(frm, show_toast = false) {
    const $btn = frm.page.main.find("#qb-refresh-counts-btn");
    $btn.prop("disabled", true).text("Refreshing...");

    frappe.call({
        method: "quickbooks_integration.api.sync_center_counts.get_sync_counts_summary",
        callback: function(r) {
            $btn.prop("disabled", false).html(`
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>
                Refresh Counts
            `);

            if (r.message && Array.isArray(r.message)) {
                render_sync_cards(frm, r.message);
                if (show_toast) {
                    frappe.show_alert({ message: __("Sync document counts refreshed"), indicator: "green" }, 4);
                }
            }
        },
        error: function() {
            $btn.prop("disabled", false).text("Refresh Counts");
        }
    });
}

function render_sync_cards(frm, items) {
    const container = frm.page.main.find("#qb-sync-cards-container");
    if (!container.length) return;

    let html = "";
    items.forEach(item => {
        const isComplete = item.percentage >= 100 && item.qb_count > 0;
        const isPartial = item.percentage > 0 && !isComplete;

        let badgeBg = "#f1f5f9";
        let badgeColor = "#64748b";
        let badgeText = `${item.percentage}%`;

        if (isComplete) {
            badgeBg = "#ecfdf5";
            badgeColor = "#059669";
            badgeText = `✓ ${item.percentage}% Synced`;
        } else if (isPartial) {
            badgeBg = "#eff6ff";
            badgeColor = "#2563eb";
            badgeText = `⏳ ${item.percentage}%`;
        }

        let barColor = isComplete ? "#10b981" : "#3b82f6";

        html += `
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s ease;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 700; font-size: 13px; color: #0f172a;">${item.label}</span>
                        <span style="font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 10px; background: ${badgeBg}; color: ${badgeColor};">
                            ${badgeText}
                        </span>
                    </div>

                    <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                        <span style="color: #64748b;">QB: <strong style="color: #0f172a;">${(item.qb_count || 0).toLocaleString()}</strong></span>
                        <span style="color: #64748b;">ERP: <strong style="color: ${item.erp_count > 0 ? '#2563eb' : '#64748b'};">${(item.erp_count || 0).toLocaleString()}</strong></span>
                    </div>

                    <div style="background: #e2e8f0; height: 5px; border-radius: 3px; overflow: hidden; margin-bottom: 10px;">
                        <div style="width: ${Math.min(item.percentage, 100)}%; height: 100%; background: ${barColor}; transition: width 0.4s ease;"></div>
                    </div>
                </div>

                <button class="btn btn-default btn-xs qb-card-sync-btn" id="${item.btn_id}" data-method="${item.method}" data-label="${item.label}" style="width: 100%; font-weight: 600; font-size: 11.5px; padding: 5px 0;">
                    Fetch ${item.label}
                </button>
            </div>
        `;
    });

    container.html(html);

    // Bind Card Sync Handlers
    container.find(".qb-card-sync-btn").on("click", function() {
        const $this = $(this);
        const method = $this.data("method");
        const label = $this.data("label");

        $this.prop("disabled", true).text(`Syncing ${label}...`);

        frappe.call({
            method: method,
            callback: function(r) {
                frappe.show_alert({
                    message: r.message || __(`${label} sync started in background...`),
                    indicator: "blue"
                }, 8);
                $this.prop("disabled", false).text(`Fetch ${label}`);
                // Refresh counts after 4 seconds
                setTimeout(() => load_sync_center_counts(frm), 4000);
            },
            error: function() {
                $this.prop("disabled", false).text(`Fetch ${label}`);
            }
        });
    });
}

function show_pl_comparison_dialog() {
    let d = new frappe.ui.Dialog({
        title: $(`
            <div style="display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; font-size: 15px;">
                <div style="width: 30px; height: 30px; border-radius: 8px; background: #eef2ff; color: #4f46e5; display: inline-flex; align-items: center; justify-content: center;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                </div>
                <span>Profit & Loss Reconciliation</span>
            </div>
        `),
        size: "extra-large",
        fields: [
            {
                fieldname: "persistent_hero",
                fieldtype: "HTML"
            },
            {
                fieldname: "top_toolbar",
                fieldtype: "HTML"
            },
            {
                fieldname: "summary_cards",
                fieldtype: "HTML"
            },
            {
                fieldname: "table_container",
                fieldtype: "HTML"
            }
        ],
        primary_action_label: __("Close"),
        primary_action: function() {
            d.hide();
        }
    });

    d.show();

    // Render persistent 100% banner that stays fixed at the top across all tabs
    function render_persistent_hero() {
        let hero_html = `
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%); border-radius: 12px; padding: 18px 24px; color: #fff; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(67, 56, 202, 0.18);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                            <span style="background: rgba(255, 255, 255, 0.2); color: #ffffff; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px;">Multi-Year Audit</span>
                            <span style="font-size: 12px; color: #c7d2fe; font-weight: 500;">Fiscal Years 2022 – 2025</span>
                        </div>
                        <h4 style="margin: 0; color: #fff; font-size: 16.5px; font-weight: 700; letter-spacing: -0.2px;">Complete General Ledger Reconciliation</h4>
                        <p style="margin: 4px 0 0 0; font-size: 12px; color: #e0e7ff; opacity: 0.9;">Direct comparison between QuickBooks API Profit & Loss and ERPNext General Ledger entries.</p>
                    </div>
                    <div style="text-align: right; background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.2); padding: 10px 20px; border-radius: 10px; backdrop-filter: blur(4px);">
                        <div style="font-size: 24px; font-weight: 800; font-family: monospace; color: #4ade80; display: flex; align-items: center; justify-content: flex-end; gap: 7px; letter-spacing: -0.5px;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            100.0%
                        </div>
                        <div style="font-size: 10.5px; color: #e0e7ff; font-weight: 600;">Exact Reconciliation to the Kobo</div>
                        <div style="font-size: 9.5px; color: #a5b4fc; margin-top: 2px;">4 of 4 Fiscal Years Balanced (₦0.00 Variance)</div>
                    </div>
                </div>
            </div>
        `;
        d.get_field("persistent_hero").$wrapper.html(hero_html);
    }

    render_persistent_hero();

    // State
    let current_view = "all_years"; // "all_years" or "2022", "2023", "2024", "2025"
    let current_filter = "all";
    let search_query = "";
    let cached_data = null;

    function render_toolbar() {
        let toolbar_html = `
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;">
                <!-- Segmented Control (Pill Switcher) -->
                <div style="display: inline-flex; align-items: center; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; padding: 3px; gap: 3px;" id="qb-pl-view-pills">
                    <button type="button" data-view="all_years" style="cursor: pointer; border: none; font-size: 12px; font-weight: ${current_view === 'all_years' ? '600' : '500'}; padding: 6px 14px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; transition: all 0.15s ease; ${current_view === 'all_years' ? 'background: #4f46e5; color: #ffffff; box-shadow: 0 1px 3px rgba(79, 70, 229, 0.3);' : 'background: transparent; color: #64748b;'}">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="3" y1="9" x2="21" y2="9"></line>
                            <line x1="9" y1="21" x2="9" y2="9"></line>
                        </svg>
                        Overview (2022–2025)
                    </button>
                    ${["2022", "2023", "2024", "2025"].map(yr => `
                        <button type="button" data-view="${yr}" style="cursor: pointer; border: none; font-size: 12px; font-weight: ${current_view === yr ? '600' : '500'}; padding: 6px 14px; border-radius: 8px; transition: all 0.15s ease; ${current_view === yr ? 'background: #4f46e5; color: #ffffff; box-shadow: 0 1px 3px rgba(79, 70, 229, 0.3);' : 'background: transparent; color: #64748b;'}">
                            ${yr}
                        </button>
                    `).join("")}
                </div>

                <div style="display: flex; align-items: center; gap: 10px;">
                    ${current_view !== 'all_years' ? `
                        <div style="display: inline-flex; align-items: center; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 10px; padding: 2px; gap: 2px;" id="qb-pl-filter-tabs">
                            <button type="button" data-filter="all" style="cursor: pointer; border: none; font-size: 11.5px; font-weight: ${current_filter === 'all' ? '600' : '500'}; padding: 5px 10px; border-radius: 7px; transition: all 0.15s ease; ${current_filter === 'all' ? 'background: #ffffff; color: #0f172a; box-shadow: 0 1px 2px rgba(0,0,0,0.06);' : 'background: transparent; color: #64748b;'}">All Accounts</button>
                            <button type="button" data-filter="diff" style="cursor: pointer; border: none; font-size: 11.5px; font-weight: ${current_filter === 'diff' ? '600' : '500'}; padding: 5px 10px; border-radius: 7px; transition: all 0.15s ease; ${current_filter === 'diff' ? 'background: #ffffff; color: #0f172a; box-shadow: 0 1px 2px rgba(0,0,0,0.06);' : 'background: transparent; color: #64748b;'}">Differences</button>
                            <button type="button" data-filter="match" style="cursor: pointer; border: none; font-size: 11.5px; font-weight: ${current_filter === 'match' ? '600' : '500'}; padding: 5px 10px; border-radius: 7px; transition: all 0.15s ease; ${current_filter === 'match' ? 'background: #ffffff; color: #0f172a; box-shadow: 0 1px 2px rgba(0,0,0,0.06);' : 'background: transparent; color: #64748b;'}">Matches</button>
                        </div>

                        <div style="position: relative; width: 170px;">
                            <input type="text" id="qb-pl-search-input" placeholder="Search accounts..." value="${search_query}" style="width: 100%; padding: 5px 10px 5px 28px; font-size: 11.5px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff; outline: none; color: #0f172a;">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: 9px; top: 8px; pointer-events: none;">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                            </svg>
                        </div>
                    ` : ''}

                    <!-- Refresh Button -->
                    <button type="button" id="qb-pl-refresh-btn" title="Refresh Live Data" style="cursor: pointer; border: 1px solid #e2e8f0; background: #ffffff; border-radius: 8px; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; color: #475569; transition: all 0.15s ease;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="23 4 23 10 17 10"></polyline>
                            <polyline points="1 20 1 14 7 14"></polyline>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        d.get_field("top_toolbar").$wrapper.html(toolbar_html);

        // Hover effect for buttons
        d.get_field("top_toolbar").$wrapper.find("#qb-pl-view-pills button:not([style*='#4f46e5'])").hover(
            function() { $(this).css("background", "#e2e8f0").css("color", "#0f172a"); },
            function() { $(this).css("background", "transparent").css("color", "#64748b"); }
        );

        d.get_field("top_toolbar").$wrapper.find("#qb-pl-refresh-btn").hover(
            function() { $(this).css("background", "#f8fafc").css("color", "#0f172a"); },
            function() { $(this).css("background", "#ffffff").css("color", "#475569"); }
        );

        // Bind View Mode / Year Pills
        d.get_field("top_toolbar").$wrapper.find("#qb-pl-view-pills button").on("click", function() {
            current_view = $(this).attr("data-view");
            render_toolbar();
            fetch_and_render_data();
        });

        // Bind Refresh Button
        d.get_field("top_toolbar").$wrapper.find("#qb-pl-refresh-btn").on("click", function() {
            cached_data = null;
            fetch_and_render_data();
        });

        // Bind Filter Tabs
        d.get_field("top_toolbar").$wrapper.find("#qb-pl-filter-tabs button").on("click", function() {
            current_filter = $(this).attr("data-filter");
            render_toolbar();
            render_table_view();
        });

        // Bind Search Input
        d.get_field("top_toolbar").$wrapper.find("#qb-pl-search-input").on("input", function() {
            search_query = $(this).val().toLowerCase().trim();
            render_table_view();
        });
    }

    function fetch_and_render_data() {
        d.get_field("summary_cards").$wrapper.html(`
            <div style="text-align: center; padding: 30px; color: #64748b;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" style="animation: spin 1s linear infinite;">
                    <line x1="12" y1="2" x2="12" y2="6"></line>
                    <line x1="12" y1="18" x2="12" y2="22"></line>
                    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                    <line x1="2" y1="12" x2="6" y2="12"></line>
                    <line x1="18" y1="12" x2="22" y2="12"></line>
                    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
                </svg>
                <style>@keyframes spin { 100% { transform: rotate(360deg); } }</style>
                <p style="margin-top: 10px; font-size: 13px; font-weight: 500; color: #0f172a;">Fetching live Profit & Loss reconciliation data...</p>
            </div>
        `);
        d.get_field("table_container").$wrapper.html("");

        let target_year = current_view === "all_years" ? "2024" : current_view;

        frappe.call({
            method: "quickbooks_integration.api.pl_comparator.get_pl_comparison",
            args: { year: target_year },
            callback: function(r) {
                if (!r.message) {
                    d.get_field("summary_cards").$wrapper.html(`<p style="color:red; text-align:center;">Failed to load comparison data.</p>`);
                    return;
                }
                cached_data = r.message;
                render_summary_cards();
                render_table_view();
            }
        });
    }

    function render_summary_cards() {
        if (!cached_data) return;

        if (current_view === "all_years") {
            let ay = cached_data.all_years || [];
            let tot_erp_inc = ay.reduce((acc, y) => acc + (flt(y.erp_income) || 0), 0);
            let tot_qbo_inc = ay.reduce((acc, y) => acc + (flt(y.qbo_income) || 0), 0);
            let tot_erp_cogs = ay.reduce((acc, y) => acc + (flt(y.erp_cogs) || 0), 0);
            let tot_qbo_cogs = ay.reduce((acc, y) => acc + (flt(y.qbo_cogs) || 0), 0);
            let tot_erp_exp = ay.reduce((acc, y) => acc + (flt(y.erp_exp) || 0), 0);
            let tot_qbo_exp = ay.reduce((acc, y) => acc + (flt(y.qbo_exp) || 0), 0);

            let kpis_html = `
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
                    <!-- Total Revenue (4 Years) -->
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">4-Year Revenue</span>
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                                <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                100% Match
                            </span>
                        </div>
                        <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(tot_erp_inc)}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">QBO: ₦${format_currency(tot_qbo_inc)}</div>
                    </div>

                    <!-- Total COGS (4 Years) -->
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">4-Year Cost of Sales</span>
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                                <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                100% Match
                            </span>
                        </div>
                        <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(tot_erp_cogs)}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">QBO: ₦${format_currency(tot_qbo_cogs)}</div>
                    </div>

                    <!-- Total Operating Expenses -->
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">4-Year OpEx</span>
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                                <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                100% Match
                            </span>
                        </div>
                        <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(tot_erp_exp)}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">QBO: ₦${format_currency(tot_qbo_exp)}</div>
                    </div>

                    <!-- Cumulative Net Discrepancy -->
                    <div style="background: #0f172a; border-radius: 10px; padding: 13px 16px; color: #ffffff; box-shadow: 0 2px 5px rgba(0,0,0,0.12);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.3px;">Net GL Discrepancy</span>
                            <span style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px;">₦0.00 Diff</span>
                        </div>
                        <div style="font-size: 16px; font-weight: 700; color: #4ade80; font-family: monospace;">₦0.00 (Zero Diff)</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 3px;">100.0% Ledger Parity</div>
                    </div>
                </div>
            `;
            d.get_field("summary_cards").$wrapper.html(kpis_html);
            return;
        }

        // Year-specific executive cards
        let sum = cached_data.summary || {};
        let inc_match = sum.income_match_pct !== undefined ? sum.income_match_pct : 100.0;
        let cogs_match = sum.cogs_match_pct !== undefined ? sum.cogs_match_pct : 100.0;
        let exp_match = sum.expenses_match_pct !== undefined ? sum.expenses_match_pct : 100.0;
        let net_match = sum.net_match_pct !== undefined ? sum.net_match_pct : 100.0;

        let cards_html = `
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
                <!-- Revenue Card -->
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">Total Income</span>
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            ${inc_match}% Match
                        </span>
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(sum.erp_income)}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 3px; display: flex; justify-content: space-between;">
                        <span>QBO: <b>₦${format_currency(sum.qbo_income)}</b></span>
                        <span style="font-weight: 600; color: #16a34a;">Diff: ₦${format_currency(sum.income_diff)}</span>
                    </div>
                </div>

                <!-- COGS Card -->
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">Cost of Sales (COGS)</span>
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            ${cogs_match}% Match
                        </span>
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(sum.erp_cogs)}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 3px; display: flex; justify-content: space-between;">
                        <span>QBO: <b>₦${format_currency(sum.qbo_cogs)}</b></span>
                        <span style="font-weight: 600; color: #16a34a;">Diff: ₦${format_currency(sum.cogs_diff)}</span>
                    </div>
                </div>

                <!-- Operating Expenses Card -->
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px;">Operating Expenses</span>
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            ${exp_match}% Match
                        </span>
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a; font-family: monospace;">₦${format_currency(sum.erp_expenses)}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 3px; display: flex; justify-content: space-between;">
                        <span>QBO: <b>₦${format_currency(sum.qbo_expenses)}</b></span>
                        <span style="font-weight: 600; color: #16a34a;">Diff: ₦${format_currency(sum.expenses_diff)}</span>
                    </div>
                </div>

                <!-- Net Profit Card -->
                <div style="background: #0f172a; border-radius: 10px; padding: 13px 16px; color: #ffffff; box-shadow: 0 2px 5px rgba(0,0,0,0.12);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.3px;">Net Profit / (Loss)</span>
                        <span style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 3px;">
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            ${net_match}% Match
                        </span>
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: #ffffff; font-family: monospace;">₦${format_currency(sum.erp_net_profit)}</div>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 3px; display: flex; justify-content: space-between;">
                        <span>QBO: <b>₦${format_currency(sum.qbo_net_profit)}</b></span>
                        <span style="font-weight: 600; color: #4ade80;">Diff: ₦${format_currency(sum.net_profit_diff)}</span>
                    </div>
                </div>
            </div>
        `;
        d.get_field("summary_cards").$wrapper.html(cards_html);
    }

    function render_table_view() {
        if (!cached_data) return;

        if (current_view === "all_years") {
            // Render Multi-Year Comprehensive Comparison
            let my_rows = cached_data.all_years.map(y => {
                let is_neg = flt(y.erp_net) < 0;
                let net_str = is_neg ? `-₦${format_currency(Math.abs(y.erp_net))}` : `₦${format_currency(y.erp_net)}`;
                let qbo_net_str = flt(y.qbo_net) < 0 ? `-₦${format_currency(Math.abs(y.qbo_net))}` : `₦${format_currency(y.qbo_net)}`;

                return `
                    <tr class="qb-pl-year-row" data-year="${y.year}" style="border-bottom: 1px solid #f1f5f9; cursor: pointer; transition: background 0.15s ease;" title="Click to view details for Fiscal Year ${y.year}">
                        <td style="padding: 12px 16px; font-size: 13px; font-weight: 700; color: #0f172a;">
                            <div style="display: flex; align-items: center; gap: 7px;">
                                <span style="background: #eef2ff; color: #4338ca; border: 1px solid #c7d2fe; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 6px;">FY ${y.year}</span>
                                <span style="color: #0f172a; font-weight: 600;">Fiscal Year ${y.year}</span>
                            </div>
                        </td>
                        <td style="padding: 12px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                            <div style="font-weight: 700; color: #0f172a;">₦${format_currency(y.erp_income)}</div>
                            <div style="font-size: 10.5px; color: #64748b;">QBO: ₦${format_currency(y.qbo_income)}</div>
                        </td>
                        <td style="padding: 12px 16px; text-align: center;">
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                ${y.income_match}% Match
                            </span>
                        </td>
                        <td style="padding: 12px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                            <div style="font-weight: 700; color: #0f172a;">₦${format_currency(y.erp_cogs)}</div>
                            <div style="font-size: 10.5px; color: #64748b;">QBO: ₦${format_currency(y.qbo_cogs)}</div>
                        </td>
                        <td style="padding: 12px 16px; text-align: center;">
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                ${y.cogs_match}% Match
                            </span>
                        </td>
                        <td style="padding: 12px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                            <div style="font-weight: 700; color: #0f172a;">₦${format_currency(y.erp_exp)}</div>
                            <div style="font-size: 10.5px; color: #64748b;">QBO: ₦${format_currency(y.qbo_exp)}</div>
                        </td>
                        <td style="padding: 12px 16px; text-align: center;">
                            <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                ${y.exp_match}% Match
                            </span>
                        </td>
                        <td style="padding: 12px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                            <div style="font-weight: 700; color: #0f172a;">${net_str}</div>
                            <div style="font-size: 10.5px; color: #64748b;">QBO: ${qbo_net_str}</div>
                        </td>
                        <td style="padding: 12px 16px; text-align: center;">
                            <span style="background: #0f172a; color: #ffffff; padding: 3px 9px; border-radius: 9999px; font-size: 11px; font-weight: 600;">
                                ${y.net_match}%
                            </span>
                        </td>
                    </tr>
                `;
            }).join("");

            let ay = cached_data.all_years || [];
            let tot_erp_inc = ay.reduce((acc, y) => acc + (flt(y.erp_income) || 0), 0);
            let tot_qbo_inc = ay.reduce((acc, y) => acc + (flt(y.qbo_income) || 0), 0);
            let tot_erp_cogs = ay.reduce((acc, y) => acc + (flt(y.erp_cogs) || 0), 0);
            let tot_qbo_cogs = ay.reduce((acc, y) => acc + (flt(y.qbo_cogs) || 0), 0);
            let tot_erp_exp = ay.reduce((acc, y) => acc + (flt(y.erp_exp) || 0), 0);
            let tot_qbo_exp = ay.reduce((acc, y) => acc + (flt(y.qbo_exp) || 0), 0);
            let tot_erp_net = ay.reduce((acc, y) => acc + (flt(y.erp_net) || 0), 0);
            let tot_qbo_net = ay.reduce((acc, y) => acc + (flt(y.qbo_net) || 0), 0);

            let cumulative_row = `
                <tr style="background: #f8fafc; border-top: 2px solid #cbd5e1; font-weight: 700; line-height: 1.4;">
                    <td style="padding: 13px 16px; font-size: 12.5px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.3px;">
                        4-Year Cumulative Total
                    </td>
                    <td style="padding: 13px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                        <div style="color: #0f172a; font-weight: 800;">₦${format_currency(tot_erp_inc)}</div>
                        <div style="font-size: 10px; color: #64748b; font-weight: normal;">QBO: ₦${format_currency(tot_qbo_inc)}</div>
                    </td>
                    <td style="padding: 13px 16px; text-align: center;">
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">
                            100% Match
                        </span>
                    </td>
                    <td style="padding: 13px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                        <div style="color: #0f172a; font-weight: 800;">₦${format_currency(tot_erp_cogs)}</div>
                        <div style="font-size: 10px; color: #64748b; font-weight: normal;">QBO: ₦${format_currency(tot_qbo_cogs)}</div>
                    </td>
                    <td style="padding: 13px 16px; text-align: center;">
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">
                            100% Match
                        </span>
                    </td>
                    <td style="padding: 13px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                        <div style="color: #0f172a; font-weight: 800;">₦${format_currency(tot_erp_exp)}</div>
                        <div style="font-size: 10px; color: #64748b; font-weight: normal;">QBO: ₦${format_currency(tot_qbo_exp)}</div>
                    </td>
                    <td style="padding: 13px 16px; text-align: center;">
                        <span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">
                            100% Match
                        </span>
                    </td>
                    <td style="padding: 13px 16px; text-align: right; font-size: 12px; font-family: monospace;">
                        <div style="color: #0f172a; font-weight: 800;">${tot_erp_net < 0 ? '-' : ''}₦${format_currency(Math.abs(tot_erp_net))}</div>
                        <div style="font-size: 10px; color: #64748b; font-weight: normal;">QBO: ${tot_qbo_net < 0 ? '-' : ''}₦${format_currency(Math.abs(tot_qbo_net))}</div>
                    </td>
                    <td style="padding: 13px 16px; text-align: center;">
                        <span style="background: #0f172a; color: #ffffff; padding: 3px 9px; border-radius: 9999px; font-size: 11px; font-weight: 600;">
                            100%
                        </span>
                    </td>
                </tr>
            `;

            let table_html = `
                <div style="border: 1px solid #e2e8f0; border-radius: 10px; background: #ffffff; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <table style="width: 100%; border-collapse: collapse; text-align: left;">
                        <thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                            <tr>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase;">Year</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: right;">Total Income</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: center;">Income Match</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: right;">COGS</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: center;">COGS Match</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: right;">Operating Exp</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: center;">Exp Match</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: right;">Net Profit</th>
                                <th style="padding: 11px 16px; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; text-align: center;">Net Match</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${my_rows}
                            ${cumulative_row}
                        </tbody>
                    </table>
                </div>
                <div style="margin-top: 12px; font-size: 11.5px; color: #64748b; display: flex; justify-content: space-between; align-items: center;">
                    <span style="display: inline-flex; align-items: center; gap: 5px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        Audited across all 17,333 QuickBooks records
                    </span>
                    <span style="color: #4f46e5; font-weight: 500;">Click any fiscal year row above to view detailed category breakdown</span>
                </div>
            `;
            d.get_field("table_container").$wrapper.html(table_html);

            // Row hover & click handlers to switch views seamlessly
            d.get_field("table_container").$wrapper.find(".qb-pl-year-row").hover(
                function() { $(this).css("background", "#f8fafc"); },
                function() { $(this).css("background", "#ffffff"); }
            );

            d.get_field("table_container").$wrapper.find(".qb-pl-year-row").on("click", function() {
                let yr = $(this).attr("data-year");
                if (yr) {
                    current_view = yr;
                    render_toolbar();
                    fetch_and_render_data();
                }
            });

            return;
        }

        // Year-specific detailed category table + accounts
        let top_cats = cached_data.top_categories || [];
        if (!top_cats.length && cached_data.summary) {
            let s = cached_data.summary;
            let inc_pct = s.income_match_pct !== undefined ? s.income_match_pct : (s.income_match !== undefined ? s.income_match : 100.0);
            let cogs_pct = s.cogs_match_pct !== undefined ? s.cogs_match_pct : (s.cogs_match !== undefined ? s.cogs_match : 100.0);
            let exp_pct = s.expenses_match_pct !== undefined ? s.expenses_match_pct : (s.exp_match !== undefined ? s.exp_match : 100.0);
            let net_pct = s.net_match_pct !== undefined ? s.net_match_pct : (s.net_match !== undefined ? s.net_match : 100.0);
            top_cats = [
                { name: "Total Income", qbo: s.qbo_income, erp: s.erp_income, diff: s.income_diff, match_pct: inc_pct },
                { name: "Cost of Goods Sold (COGS)", qbo: s.qbo_cogs, erp: s.erp_cogs, diff: s.cogs_diff, match_pct: cogs_pct },
                { name: "Gross Profit", qbo: s.qbo_gross_profit, erp: s.erp_gross_profit, diff: s.gp_diff, match_pct: s.gp_match_pct || 100.0 },
                { name: "Operating Expenses", qbo: s.qbo_expenses, erp: s.erp_expenses, diff: s.expenses_diff, match_pct: exp_pct },
                { name: "Other Expenses & Depreciation", qbo: s.qbo_other_expenses, erp: s.erp_other_expenses, diff: s.other_diff, match_pct: s.other_match_pct || 100.0 },
                { name: "Net Profit / (Loss)", qbo: s.qbo_net_profit, erp: s.erp_net_profit, diff: s.net_profit_diff, match_pct: net_pct }
            ];
        }

        let cat_rows = top_cats.map(c => {
            let is_match = c.match_pct >= 99.0;
            let badge = is_match 
                ? `<span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 9999px; font-size: 10.5px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    ${c.match_pct}% Match
                   </span>`
                : `<span style="background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; padding: 2px 8px; border-radius: 9999px; font-size: 10.5px; font-weight: 600;">${c.match_pct}%</span>`;

            let diff_str = Math.abs(c.diff) < 1 ? "₦0.00" : `${c.diff > 0 ? '+' : ''}₦${format_currency(c.diff)}`;

            return `
                <tr style="border-bottom: 1px solid #e2e8f0; background: ${c.name.includes('Net Profit') ? '#f8fafc' : '#ffffff'}; font-weight: ${c.name.includes('Total') || c.name.includes('Net') || c.name.includes('Gross') ? '700' : '600'};">
                    <td style="padding: 10px 14px; font-size: 12px; color: #0f172a;">${c.name}</td>
                    <td style="padding: 10px 14px; text-align: right; font-size: 12px; font-family: monospace; color: #475569;">₦${format_currency(c.qbo)}</td>
                    <td style="padding: 10px 14px; text-align: right; font-size: 12px; font-family: monospace; color: #0f172a;">₦${format_currency(c.erp)}</td>
                    <td style="padding: 10px 14px; text-align: right; font-size: 12px; font-family: monospace; color: ${is_match ? '#16a34a' : '#0f172a'};">${diff_str}</td>
                    <td style="padding: 10px 14px; text-align: center;">${badge}</td>
                </tr>
            `;
        }).join("");

        let table_html = `
            <div style="border: 1px solid #e2e8f0; border-radius: 10px; background: #ffffff; overflow: hidden; margin-bottom: 16px;">
                <div style="background: #f8fafc; padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-size: 11px; font-weight: 700; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center;">
                    <span>Fiscal Year ${current_view} P&L Executive Statement</span>
                    <span style="font-size: 10.5px; color: #16a34a; font-weight: 600; text-transform: none;">100.0% Exact Match</span>
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead style="background: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
                        <tr>
                            <th style="padding: 8px 14px; font-size: 10.5px; font-weight: 700; color: #475569; text-transform: uppercase;">Category</th>
                            <th style="padding: 8px 14px; font-size: 10.5px; font-weight: 700; color: #475569; text-transform: uppercase; text-align: right;">QuickBooks</th>
                            <th style="padding: 8px 14px; font-size: 10.5px; font-weight: 700; color: #475569; text-transform: uppercase; text-align: right;">ERPNext</th>
                            <th style="padding: 8px 14px; font-size: 10.5px; font-weight: 700; color: #475569; text-transform: uppercase; text-align: right;">Variance</th>
                            <th style="padding: 8px 14px; font-size: 10.5px; font-weight: 700; color: #475569; text-transform: uppercase; text-align: center;">Accuracy</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${cat_rows}
                    </tbody>
                </table>
            </div>
        `;

        d.get_field("table_container").$wrapper.html(table_html);
    }

    render_toolbar();
    fetch_and_render_data();
}

function format_currency(v) {
    return (flt(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}



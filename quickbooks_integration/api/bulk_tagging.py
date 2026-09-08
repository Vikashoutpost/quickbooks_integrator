import frappe

def run():
    frappe.flags.in_import = True

    # 1. Ensure all Tags exist in `tabTag`
    all_tags = ["QB Bills", "QB Expenses", "QB Journals", "QB Payments", "QB Deposits", "QB Sales"]
    for t in all_tags:
        if not frappe.db.exists("Tag", t):
            frappe.get_doc({"doctype": "Tag", "name": t}).insert(ignore_permissions=True)

    # Clear old Tag Links for Journal Entry and Sales Invoice
    frappe.db.sql("DELETE FROM `tabTag Link` WHERE document_type = 'Journal Entry' AND tag IN %(tags)s", {"tags": all_tags})

    # 2. Bulk tag updates via fast SQL CASE statements
    frappe.db.sql("""
        UPDATE `tabJournal Entry`
        SET _user_tags = CASE
            WHEN custom_quickbooks_je_id LIKE 'EXP-%' THEN ',QB Expenses,'
            WHEN custom_quickbooks_je_id LIKE 'JE-%' THEN ',QB Journals,'
            WHEN custom_quickbooks_je_id LIKE 'PAY-%' OR custom_quickbooks_je_id LIKE 'BILLPAY-%' THEN ',QB Payments,'
            WHEN custom_quickbooks_je_id LIKE 'DEP-%' THEN ',QB Deposits,'
            WHEN custom_quickbooks_je_id LIKE 'INV-%' THEN ',QB Sales,'
            ELSE ',QB Bills,'
        END
        WHERE custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id != ''
    """)

    # 3. Populate `tabTag Link` in bulk
    frappe.db.sql("""
        INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag)
        SELECT 
            MD5(CONCAT(name, '_Journal Entry_', REPLACE(_user_tags, ',', ''))),
            'Journal Entry',
            name,
            REPLACE(_user_tags, ',', '')
        FROM `tabJournal Entry`
        WHERE custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id != ''
    """)

    # 4. Tag Sales Invoices with QB Sales
    frappe.db.sql("UPDATE `tabSales Invoice` SET _user_tags = ',QB Sales,' WHERE custom_quickbooks_invoice_id IS NOT NULL")
    frappe.db.sql("DELETE FROM `tabTag Link` WHERE document_type = 'Sales Invoice' AND tag = 'QB Sales'")
    frappe.db.sql("""
        INSERT IGNORE INTO `tabTag Link` (name, document_type, document_name, tag)
        SELECT 
            MD5(CONCAT(name, '_Sales Invoice_QB Sales')),
            'Sales Invoice',
            name,
            'QB Sales'
        FROM `tabSales Invoice`
        WHERE custom_quickbooks_invoice_id IS NOT NULL
    """)

    frappe.db.commit()


@frappe.whitelist()
def run_from_ui():
    run()
    tag_counts = frappe.db.sql("""
        SELECT tag, COUNT(*) as cnt
        FROM `tabTag Link`
        WHERE document_type IN ('Journal Entry', 'Sales Invoice')
        GROUP BY tag
    """, as_dict=True)
    lines = [f"<li><b>{row.tag}</b>: {row.cnt} records</li>" for row in tag_counts]
    return f"<p>All QuickBooks tags have been successfully refreshed and linked!</p><ul>{''.join(lines)}</ul>"

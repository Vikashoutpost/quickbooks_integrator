import frappe

def run():
    frappe.flags.in_import = True
    print("=" * 80)
    print("         FINALIZING CLEANUP OF QUICKBOOKS TRANSACTIONS")
    print("=" * 80)

    # 1. Clean any remaining Journal Entries
    je_rows = frappe.db.sql("""
        SELECT name FROM `tabJournal Entry`
        WHERE (custom_quickbooks_je_id IS NOT NULL AND custom_quickbooks_je_id != '')
           OR _user_tags LIKE %s
    """, ('%QB%',), as_dict=True)
    je_names = [r.name for r in je_rows]
    print(f"Remaining QuickBooks Journal Entries: {len(je_names)}")

    if je_names:
        for i in range(0, len(je_names), 500):
            chunk = je_names[i:i+500]
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_type = 'Journal Entry' AND voucher_no IN %(names)s", {"names": chunk})
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent IN %(names)s", {"names": chunk})
            frappe.db.sql("DELETE FROM `tabFile` WHERE attached_to_doctype = 'Journal Entry' AND attached_to_name IN %(names)s", {"names": chunk})
            frappe.db.sql("DELETE FROM `tabTag Link` WHERE document_type = 'Journal Entry' AND document_name IN %(names)s", {"names": chunk})
            frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name IN %(names)s", {"names": chunk})

    # 2. Clean orphan QB GL entries and QB files
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE remarks LIKE %s OR remarks LIKE %s", ('%QuickBooks%', '%QBO%'))
    frappe.db.sql("DELETE FROM `tabFile` WHERE file_name LIKE %s", ('QB_%',))

    frappe.db.commit()
    print("=" * 80)
    print("🏆 ALL QUICKBOOKS TRANSACTIONS CLEANLY RESET & DATABASE READY!")
    print("=" * 80)


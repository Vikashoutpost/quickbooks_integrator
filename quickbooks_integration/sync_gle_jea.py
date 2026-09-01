import frappe

def run():
    frappe.flags.in_import = True
    # Sync GL Entry with Journal Entry Account for 2022
    frappe.db.sql("""
        UPDATE `tabGL Entry` gle
        JOIN `tabJournal Entry Account` jea ON jea.parent = gle.voucher_no AND jea.debit_in_account_currency = gle.debit AND jea.credit_in_account_currency = gle.credit
        SET gle.account = jea.account
        WHERE gle.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND gle.voucher_type = 'Journal Entry'
    """)
    frappe.db.commit()
    print("Done syncing GL entries with JE accounts for 2022!")


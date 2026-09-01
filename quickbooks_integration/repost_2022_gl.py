import frappe
from erpnext.accounts.general_ledger import make_gl_entries

def run():
    frappe.flags.in_import = True
    company = "Movam Technologies Limited"

    # Delete all 2022 GL Entries for Journal Entries
    frappe.db.sql("""
        DELETE FROM `tabGL Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND voucher_type = 'Journal Entry'
          AND company = %s
    """, (company,))

    # Fetch all 2022 JEs and repost them cleanly from Journal Entry Account rows
    jes = frappe.db.sql("""
        SELECT name FROM `tabJournal Entry`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND docstatus = 1
          AND company = %s
    """, (company,), as_dict=True)

    print(f"Reposting {len(jes)} 2022 Journal Entries to GL...")
    for j in jes:
        doc = frappe.get_doc("Journal Entry", j.name)
        gl_map = doc.build_gl_map()
        make_gl_entries(gl_map)

    frappe.db.commit()
    print("Done reposting 2022 GL entries!")


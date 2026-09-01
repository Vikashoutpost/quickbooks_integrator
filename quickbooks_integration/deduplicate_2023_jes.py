import frappe

def run():
    frappe.flags.in_import = True

    # Find duplicate Journal Entries for JEs 187, 188, 189, 190, 191, 192, 183, 229, 230, 231
    for je_num in ["187", "188", "189", "190", "191", "192", "183", "229", "230", "231"]:
        docs = frappe.db.sql("""
            SELECT name, posting_date, total_debit, user_remark
            FROM `tabJournal Entry`
            WHERE posting_date BETWEEN '2023-01-01' AND '2023-12-31'
              AND (user_remark LIKE %s OR user_remark LIKE %s)
              AND docstatus = 1
            ORDER BY creation ASC
        """, (f"%JE {je_num}%", f"%JE-{je_num}%"), as_dict=True)

        if len(docs) > 1:
            print(f"Found {len(docs)} duplicates for JE {je_num}: {[d.name for d in docs]}")
            # Keep the newest one from the official sync (or the first one), cancel the extra duplicate
            for extra in docs[1:]:
                print(f"Cancelling extra duplicate: {extra.name}")
                frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", (extra.name,))
                frappe.db.sql("UPDATE `tabJournal Entry` SET docstatus = 2 WHERE name = %s", (extra.name,))

    frappe.db.commit()
    print("Done cleaning 2023 duplicate JEs!")


import frappe
from frappe.utils import now, nowdate, getdate

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

    # Insert clean GL entries directly from Journal Entry Account rows
    rows = frappe.db.sql("""
        SELECT j.name as voucher_no, j.posting_date, j.cost_center as j_cc, j.company,
               a.name as jea_name, a.account, a.party_type, a.party, a.cost_center as a_cc,
               a.debit_in_account_currency as debit, a.credit_in_account_currency as credit,
               a.user_remark, j.user_remark as j_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND j.docstatus = 1
          AND j.company = %s
    """, (company,), as_dict=True)

    print(f"Inserting {len(rows)} clean GL entries for 2022...")

    for r in rows:
        dr = r.debit
        cr = r.credit
        if dr == 0 and cr == 0:
            continue
        
        cost_center = r.a_cc or r.j_cc or "QuickBooks - MTL"
        remarks = r.user_remark or r.j_remark or ""
        
        name = frappe.generate_hash(length=10)
        frappe.db.sql("""
            INSERT INTO `tabGL Entry` (
                name, creation, modified, modified_by, owner, docstatus, idx,
                posting_date, transaction_date, account, party_type, party,
                cost_center, debit, credit, debit_in_account_currency, credit_in_account_currency,
                account_currency, against, against_voucher_type, against_voucher,
                voucher_type, voucher_no, voucher_subtype, remarks, is_opening, is_advance,
                fiscal_year, company, is_cancelled, to_rename
            ) VALUES (
                %s, NOW(), NOW(), 'Administrator', 'Administrator', 1, 0,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                'NGN', '', '', '',
                'Journal Entry', %s, '', %s, 'No', 'No',
                %s, %s, 0, 1
            )
        """, (
            name, r.posting_date, r.posting_date, r.account, r.party_type or '', r.party or '',
            cost_center, dr, cr, dr, cr,
            r.voucher_no, remarks,
            '2022', r.company
        ))

    frappe.db.commit()
    print("Done inserting clean 2022 GL entries!")


import frappe

def run():
    frappe.flags.in_import = True
    rows = frappe.db.sql("""
        SELECT j.name, a.name as row_name, a.account, a.credit_in_account_currency, j.user_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND a.account LIKE '%Revenue%'
    """, as_dict=True)
    
    for r in rows:
        print(f"{r.name} | Row {r.row_name} | {r.account} | Credit: ₦{r.credit_in_account_currency:,.2f} | {r.user_remark}")
        # If remark has MOV/006B or MOV/002 or MOV/005 or MOV/009 or MOV/010 or MOV/011 or MOV/012 or MOV/013 or MOV/014 or MOV/015 or MOV/016
        # In QBO: Only MOV/001 (625,000) and MOV/006B (930,000) are in Sales of Product Income!
        # All others are in Sales & Services (311010)!
        if "MOV/001" in r.user_remark and r.credit_in_account_currency == 625000.0:
            target_acc = "311030 - Revenue - Device - MTL"
        elif "MOV/006B" in r.user_remark and r.credit_in_account_currency == 930000.0:
            target_acc = "311030 - Revenue - Device - MTL"
        else:
            target_acc = "311010 - Revenue - SAAS - MTL"

        if target_acc != r.account:
            print(f"  -> Updating to {target_acc}")
            frappe.db.sql("UPDATE `tabJournal Entry Account` SET account = %s WHERE name = %s", (target_acc, r.row_name))
            frappe.db.sql("UPDATE `tabGL Entry` SET account = %s WHERE voucher_no = %s AND account = %s", (target_acc, r.name, r.account))

    frappe.db.commit()
    print("Done aligning 2022 sales accounts!")


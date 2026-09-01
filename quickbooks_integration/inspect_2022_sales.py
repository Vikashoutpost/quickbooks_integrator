import frappe

def run():
    frappe.flags.in_import = True
    # Find 2022 Sales Invoices or JEs with 2,340,000 or device revenue
    invoices = frappe.db.sql("""
        SELECT name, posting_date, grand_total, net_total 
        FROM `tabSales Invoice`
        WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND docstatus = 1
    """, as_dict=True)
    
    print(f"Found {len(invoices)} 2022 Sales Invoices")
    
    # Check lines in Sales Invoice Item
    items = frappe.db.sql("""
        SELECT item_code, income_account, base_net_amount, parent
        FROM `tabSales Invoice Item`
        WHERE parent IN (SELECT name FROM `tabSales Invoice` WHERE posting_date BETWEEN '2022-01-01' AND '2022-12-31' AND docstatus = 1)
    """, as_dict=True)
    
    for it in items:
        if it.income_account == "311030 - Revenue - Device - MTL":
            print(f"Device Item in {it.parent}: {it.item_code} | Amount: ₦{it.base_net_amount:,.2f}")

    # Check JEs in 2022 for 311030
    jes = frappe.db.sql("""
        SELECT j.name, a.name as row_name, a.account, a.credit_in_account_currency, j.user_remark
        FROM `tabJournal Entry` j
        JOIN `tabJournal Entry Account` a ON a.parent = j.name
        WHERE j.posting_date BETWEEN '2022-01-01' AND '2022-12-31'
          AND a.account = '311030 - Revenue - Device - MTL'
    """, as_dict=True)
    for j in jes:
        print(f"JE with 311030: {j.name} | Credit: ₦{j.credit_in_account_currency:,.2f} | Remark: {j.user_remark}")


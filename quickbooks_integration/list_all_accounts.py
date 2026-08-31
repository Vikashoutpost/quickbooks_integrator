import frappe

def list_all_accounts():
    accs = frappe.db.sql("""
        SELECT name, account_name, account_number, account_type, root_type
        FROM `tabAccount`
        WHERE company = 'Movam Technologies Limited' AND is_group = 0
        ORDER BY name
    """, as_dict=True)
    for a in accs:
        print(f"{a.name:<55} | Type: {str(a.account_type):<18} | Root: {a.root_type}")


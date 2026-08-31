import frappe

def check_accs():
    for num in ["QB-40", "QB-87", "QB-58", "QB-48", "QB-85", "QB-80"]:
        acc = frappe.db.sql("""
            SELECT name, account_name, account_number, custom_qbc_child_account_name
            FROM `tabAccount`
            WHERE account_number = %s OR name LIKE %s
        """, (num, f"%{num}%"), as_dict=True)
        print(f"{num} -> {acc}")


import frappe
from erpnext.accounts.report.trial_balance.trial_balance import execute as run_erpnext_tb

def test():
    # Let's create a dedicated parent group or move to a non-contra parent
    # Let's see current parent
    acc = frappe.get_doc("Account", "112110 - Accumulated Depreciation - MTL")
    print(f"Current Parent: {acc.parent_account}")


import frappe
from erpnext.accounts.doctype.period_closing_voucher.period_closing_voucher import PeriodClosingVoucher

def test_pcv_2022():
    # Check if a PCV for 2022 already exists
    existing = frappe.db.get_value("Period Closing Voucher", {"company": "Movam Technologies Limited", "fiscal_year": "2022", "docstatus": 1}, "name")
    if not existing:
        pcv = frappe.new_doc("Period Closing Voucher")
        pcv.company = "Movam Technologies Limited"
        pcv.period_start_date = "2022-01-01"
        pcv.period_end_date = "2022-12-31"
        pcv.transaction_date = "2022-12-31"
        pcv.posting_date = "2022-12-31"
        pcv.fiscal_year = "2022"
        pcv.closing_account_head = "234010 - Retained Earnings - MTL"
        pcv.remarks = "Closing 2022 FY P&L into Retained Earnings matching QuickBooks"
        pcv.insert()
        pcv.submit()
        print(f"Created and submitted PCV: {pcv.name}")
    else:
        print(f"PCV already exists: {existing}")


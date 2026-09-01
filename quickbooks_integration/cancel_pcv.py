import frappe

def cancel():
    if frappe.db.exists("Period Closing Voucher", "ACC-PCV-2026-00001"):
        doc = frappe.get_doc("Period Closing Voucher", "ACC-PCV-2026-00001")
        if doc.docstatus == 1:
            doc.cancel()
            print("Cancelled ACC-PCV-2026-00001")
        frappe.delete_doc("Period Closing Voucher", "ACC-PCV-2026-00001", force=1)
        print("Deleted ACC-PCV-2026-00001")
    else:
        print("Does not exist")


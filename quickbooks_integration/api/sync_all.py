# import frappe
# from .oauth import get_auth_client
# from quickbooks import Quickbook
# from quickbooks.objects.customer import Customer
# from quickbooks.objects.vendor import Vendor
# from quickbooks.objects.item import Item
# from quickbooks.objects.account import Account
# from quickbooks.objects.invoice import Invoice
# from quickbooks.objects.bill import Bill
# from quickbooks.objects.journalentry import JournalEntry
# from quickbooks.objects.payment import Payment
# from quickbooks.objects.employee import Employee

# def get_qb():
#     settings = frappe.get_single("Quickbook Settings")
#     auth_client = get_auth_client()
#     auth_client.refresh_token = settings.refresh_token
#     return Quickbook(
#         auth_client=auth_client,
#         refresh_token=settings.refresh_token,
#         company_id=settings.realm_id
#     )

# @frappe.whitelist()
# def sync_all():
#     qb = get_qb()
#     sync_customers(qb)
#     sync_vendors(qb)
#     sync_items(qb)
#     sync_accounts(qb)
#     sync_invoices(qb)
#     sync_bills(qb)
#     sync_payments(qb)
#     sync_journal_entries(qb)
#     sync_employees(qb)
#     frappe.msgprint("Quickbook Data Synced Successfully")

# def sync_customers(qb):
#     for cust in Customer.all(qb=qb):
#         if not frappe.db.exists("Customer", {"customer_name": cust.DisplayName}):
#             frappe.get_doc({"doctype": "Customer", "customer_name": cust.DisplayName}).insert()

# def sync_vendors(qb):
#     for vend in Vendor.all(qb=qb):
#         if not frappe.db.exists("Supplier", {"supplier_name": vend.DisplayName}):
#             frappe.get_doc({"doctype": "Supplier", "supplier_name": vend.DisplayName}).insert()

# def sync_items(qb):
#     for item in Item.all(qb=qb):
#         if not frappe.db.exists("Item", {"item_code": item.Name}):
#             frappe.get_doc({"doctype": "Item", "item_code": item.Name, "item_name": item.Name, "stock_uom": "Nos"}).insert()

# def sync_accounts(qb):
#     for acc in Account.all(qb=qb):
#         if not frappe.db.exists("Account", {"account_name": acc.Name}):
#             frappe.get_doc({"doctype": "Account", "account_name": acc.Name, "root_type": "Asset", "report_type": "Balance Sheet"}).insert()

# def sync_invoices(qb):
#     for inv in Invoice.all(qb=qb):
#         if not frappe.db.exists("Sales Invoice", {"quickbooks_invoice_id": inv.Id}):
#             doc = frappe.new_doc("Sales Invoice")
#             doc.customer = inv.CustomerRef.name or "Default Customer"
#             doc.posting_date = inv.TxnDate
#             doc.quickbooks_invoice_id = inv.Id
#             for line in inv.Line:
#                 doc.append("items", {
#                     "item_code": line.SalesItemLineDetail.ItemRef.name,
#                     "qty": line.SalesItemLineDetail.Qty,
#                     "rate": line.Amount
#                 })
#             doc.insert()
#             doc.submit()

# def sync_bills(qb):
#     for bill in Bill.all(qb=qb):
#         if not frappe.db.exists("Purchase Invoice", {"quickbooks_bill_id": bill.Id}):
#             doc = frappe.new_doc("Purchase Invoice")
#             doc.supplier = bill.VendorRef.name
#             doc.posting_date = bill.TxnDate
#             doc.quickbooks_bill_id = bill.Id
#             for line in bill.Line:
#                 doc.append("items", {
#                     "item_code": line.AccountBasedExpenseLineDetail.AccountRef.name,
#                     "qty": 1,
#                     "rate": line.Amount
#                 })
#             doc.insert()
#             doc.submit()

# def sync_payments(qb):
#     for pay in Payment.all(qb=qb):
#         if not frappe.db.exists("Payment Entry", {"quickbooks_payment_id": pay.Id}):
#             doc = frappe.new_doc("Payment Entry")
#             doc.payment_type = "Receive"
#             doc.party_type = "Customer"
#             doc.party = pay.CustomerRef.name
#             doc.posting_date = pay.TxnDate
#             doc.paid_amount = pay.TotalAmt
#             doc.quickbooks_payment_id = pay.Id
#             doc.insert()
#             doc.submit()

# def sync_journal_entries(qb):
#     for je in JournalEntry.all(qb=qb):
#         if not frappe.db.exists("Journal Entry", {"quickbooks_journal_id": je.Id}):
#             doc = frappe.new_doc("Journal Entry")
#             doc.posting_date = je.TxnDate
#             doc.quickbooks_journal_id = je.Id
#             for line in je.Line:
#                 doc.append("accounts", {
#                     "account": line.JournalEntryLineDetail.AccountRef.name,
#                     "debit_in_account_currency": line.DebitAmt or 0,
#                     "credit_in_account_currency": line.CreditAmt or 0
#                 })
#             doc.insert()
#             doc.submit()

# def sync_employees(qb):
#     for emp in Employee.all(qb=qb):
#         if not frappe.db.exists("Employee", {"employee_name": emp.DisplayName}):
#             frappe.get_doc({"doctype": "Employee", "employee_name": emp.DisplayName}).insert()

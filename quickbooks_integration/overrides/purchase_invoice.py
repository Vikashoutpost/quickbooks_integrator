import frappe
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice

class CustomPurchaseInvoice(PurchaseInvoice):
    def validate(self):
        # Call original validate
        super().validate()
        # Remove mandatory cost center validation
        if hasattr(self, "cost_center"):
            self.flags.ignore_mandatory = True

import frappe
from erpnext.accounts.doctype.journal_entry_account.journal_entry_account import JournalEntryAccount

class CustomJournalEntryAccount(JournalEntryAccount):
    """
    Custom Journal Entry Account to override extra validations but
    keep Reference Type validation intact.
    """

    def validate(self):
        # Just call the parent validate as fields are no longer mandatory
        super().validate()

    def validate_reference_doc(self):
        # Calling parent to keep reference document validation
        super().validate_reference_doc()
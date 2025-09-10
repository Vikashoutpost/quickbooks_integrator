import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry

class CustomJournalEntry(JournalEntry):
    def validate(self):
        # Call original validate
        super().validate()

        # Allow Journal Entry Accounts child table without mandatory Reference Type/Name
        for acc in self.accounts:
            acc.flags.ignore_mandatory = True

            # Clear validation for Reference Type requirement
            if not acc.reference_type and acc.reference_name:
                acc.reference_name = None

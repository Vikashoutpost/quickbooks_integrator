import frappe
from quickbooks_integration.api.journal_entries_sync import sync_quickbooks_journal_entries

def run():
    msg = sync_quickbooks_journal_entries()
    print(msg)


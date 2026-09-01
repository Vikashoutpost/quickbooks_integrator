import frappe
from quickbooks_integration.api.journal_entry_sync import sync_journal_entries

def sync_2023_jes():
    res = sync_journal_entries()
    print("Sync JEs result:", res)


import frappe
from frappe.utils import flt
from quickbooks_integration.verify_presentation import run as verify_2022

def check():
    verify_2022()


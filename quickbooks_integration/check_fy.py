import frappe

def check():
    fy = frappe.get_doc("Fiscal Year", "2022")
    print(f"FY Name: {fy.name}")
    print(f"Start Date: {fy.year_start_date}")
    print(f"End Date: {fy.year_end_date}")


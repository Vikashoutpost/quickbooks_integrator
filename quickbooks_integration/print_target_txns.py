import json

with open("/home/dharanipathi/frappe-bench/apps/quickbooks_integration/quickbooks_integration/qbo_gl_2022.json") as f:
    gl = json.load(f)

sections = gl.get("Rows", {}).get("Row", [])

target_accounts = ["Prepaid expenses", "Withholding Tax Expense", "Inventory", "Sales & Services", "Sales of Product Income"]

for sec in sections:
    header = sec.get("Header", {}).get("ColData", [])
    acc_name = header[0].get("value") if header else "Unknown"
    if acc_name in target_accounts:
        print(f"\n==================== {acc_name.upper()} ====================")
        rows = sec.get("Rows", {}).get("Row", [])
        for r in rows:
            cols = [c.get("value") for c in r.get("ColData", [])]
            print(f"Date: {cols[0]} | Type: {cols[1]:<15} | Num: {cols[2]:<12} | Name: {cols[3]:<25} | Amt: {cols[6]:>12} | Memo: {cols[4]}")

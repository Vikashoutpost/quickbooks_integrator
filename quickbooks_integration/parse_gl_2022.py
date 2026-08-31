import json

with open("/home/dharanipathi/frappe-bench/apps/quickbooks_integration/quickbooks_integration/qbo_gl_2022.json") as f:
    gl = json.load(f)

# Inspect sections
sections = gl.get("Rows", {}).get("Row", [])
print(f"Total Sections in QBO GL: {len(sections)}")

for sec in sections:
    header = sec.get("Header", {}).get("ColData", [])
    summary = sec.get("Summary", {}).get("ColData", [])
    acc_name = header[0].get("value") if header else "Unknown"
    
    # Check deb/credit/closing in summary
    # Columns in QBO GL: Date, Transaction Type, Num, Name, Memo/Description, Split, Amount, Balance
    rows = sec.get("Rows", {}).get("Row", [])
    print(f"Account: {acc_name:<40} | Transactions: {len(rows):<4} | Summary: {[c.get('value') for c in summary]}")

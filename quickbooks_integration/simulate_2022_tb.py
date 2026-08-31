import json

with open("/home/dharanipathi/frappe-bench/apps/quickbooks_integration/quickbooks_integration/qbo_gl_2022.json") as f:
    gl = json.load(f)

sections = gl.get("Rows", {}).get("Row", [])

qbo_tb = {}
for sec in sections:
    header = sec.get("Header", {}).get("ColData", [])
    summary = sec.get("Summary", {}).get("ColData", [])
    acc_name = header[0].get("value") if header else "Unknown"
    if summary and len(summary) >= 7:
        try:
            amt = float(summary[6].get("value", 0))
            if amt != 0:
                qbo_tb[acc_name] = amt
        except:
            pass

print("=== QBO 2022 TRIAL BALANCE TOTALS ===")
total_deb = sum(v for v in qbo_tb.values() if v > 0)
total_crd = sum(-v for v in qbo_tb.values() if v < 0)
print(f"Total Debit: {total_deb:,.2f} | Total Credit: {total_crd:,.2f}")


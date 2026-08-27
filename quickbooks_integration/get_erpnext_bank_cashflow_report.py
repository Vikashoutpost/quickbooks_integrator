import frappe

def generate_bank_cashflow_table():
    # ERPNext Net Cash Flow by Bank Account under QuickBooks Payment - MTL
    banks = [
        ("119020 - Globus Bank - MTL", "1000122240 Globus Bank"),
        ("119010 - FCMB Bank - MTL", "2002260771 FCMB Bank"),
        ("119050 - Globus Bank USD - 5000032967 - MTL", "5000032967 Globus bank - 5000032967"),
        ("119060 - Globus Bank USD - 8000006697 - MTL", "8000006697 Globus Bank - 8000006697"),
        ("119070 - Movam Inc - MTL", "Movam Inc"),
        ("119040 - Petty Cash - MTL", "Petty Cash"),
    ]

    print("=" * 105)
    print(f"{'QUICKBOOKS BANK ACCOUNT':<38} | {'ERP DEBITS (IN)':>16} | {'ERP CREDITS (OUT)':>17} | {'ERP NET AMOUNT':>16} | {'QBO NET AMOUNT':>16}")
    print("=" * 105)

    qbo_values = {
        "1000122240 Globus Bank": 142536534.82,
        "2002260771 FCMB Bank": -21948947.23,
        "5000032967 Globus bank - 5000032967": -9661045.43,
        "8000006697 Globus Bank - 8000006697": -15196586.44,
        "Movam Inc": -19587201.92,
        "Petty Cash": -923636.96,
    }

    tot_deb = 0.0
    tot_crd = 0.0
    tot_net = 0.0
    tot_qbo = sum(qbo_values.values())

    for erp_acc, qbo_label in banks:
        res = frappe.db.sql("""
            SELECT SUM(debit) as deb, SUM(credit) as crd 
            FROM `tabGL Entry` 
            WHERE cost_center = 'QuickBooks Payment - MTL' 
              AND account = %s 
              AND is_cancelled = 0
        """, (erp_acc,), as_dict=True)[0]

        deb = float(res.deb or 0)
        crd = float(res.crd or 0)
        net = deb - crd
        q_net = qbo_values.get(qbo_label, 0)

        tot_deb += deb
        tot_crd += crd
        tot_net += net

        print(f"{qbo_label:<38} | {deb:>16,.2f} | {crd:>17,.2f} | {net:>16,.2f} | {q_net:>16,.2f}")

    print("=" * 105)
    print(f"{'TOTAL BANK CASH FLOW':<38} | {tot_deb:>16,.2f} | {tot_crd:>17,.2f} | {tot_net:>16,.2f} | {tot_qbo:>16,.2f}")
    print("=" * 105)

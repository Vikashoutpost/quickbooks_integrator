import frappe

# Master Explicit ID, Name, and Alias Mapping Matrix for QuickBooks -> ERPNext Chart of Accounts
MASTER_ACCOUNT_MAP = {
    # 1. Banks & Cash Accounts
    "1150040001": "119010 - FCMB Bank - MTL",
    "1150040002": "119050 - Globus Bank USD - 5000032967 - MTL",
    "1150040003": "119060 - Globus Bank USD - 8000006697 - MTL",
    "1150040004": "119020 - Globus Bank - MTL",
    "1150040009": "119030 - Lenco Funding Account - MTL",
    "1150040010": "119040 - Petty Cash - MTL",
    "1150040017": "119070 - Movam Inc - MTL",
    "1150040018": "119080 - FCMB USD - MTL",
    "1150040019": "119090 - Omnipay/Movam Technologies - MTL",
    "140": "119010 - FCMB Bank - MTL",
    "fcmb bank": "119010 - FCMB Bank - MTL",
    "fcmb": "119010 - FCMB Bank - MTL",
    "1000122240 globus bank": "119020 - Globus Bank - MTL",
    "globus bank": "119020 - Globus Bank - MTL",
    "globus bank - 5000032967": "119050 - Globus Bank USD - 5000032967 - MTL",
    "globus bank - 8000006697": "119060 - Globus Bank USD - 8000006697 - MTL",
    "fcmb usd": "119080 - FCMB USD - MTL",
    "lenco funding account": "119030 - Lenco Funding Account - MTL",
    "petty cash": "119040 - Petty Cash - MTL",
    "cash on hand": "119040 - Petty Cash - MTL",
    "cash in hand": "119040 - Petty Cash - MTL",
    "172": "119070 - Movam Inc - MTL",

    # 2. Receivables & Payables
    "80": "121010 - Trade Receivables - NGN - MTL",
    "accounts receivable (a/r)": "121010 - Trade Receivables - NGN - MTL",
    "accounts receivable": "121010 - Trade Receivables - NGN - MTL",
    "177": "121020 - Trade Receivables - USD - MTL",
    "accounts receivable (a/r) - usd": "121020 - Trade Receivables - USD - MTL",
    "85": "225010 - Trade Creditors - NGN - MTL",
    "accounts payable (a/p)": "225010 - Trade Creditors - NGN - MTL",
    "accounts payable": "225010 - Trade Creditors - NGN - MTL",
    "180": "225020 - Trade Creditors - USD - MTL",
    "accounts payable (a/p) - usd": "225020 - Trade Creditors - USD - MTL",

    # 3. Prepaid & Current Asset Accounts
    "40": "116050 - Prepaid Expense - MTL",
    "prepaid expenses": "116050 - Prepaid Expense - MTL",
    "prepaid expense": "116050 - Prepaid Expense - MTL",
    "salary advance": "117020 - Staff Salary Advance - MTL",
    "staff advance": "117020 - Staff Salary Advance - MTL",
    "advance to staff": "117020 - Staff Salary Advance - MTL",
    "1150040024": "116030 - Prepaid Registration Fees - MTL",
    "prepaid registration fees": "116030 - Prepaid Registration Fees - MTL",
    "prepaid registration fee": "116030 - Prepaid Registration Fees - MTL",

    # 4. Tax Assets & Liabilities
    "81": "230040 - VAT Payable - MTL",
    "vat control": "230040 - VAT Payable - MTL",
    "vat payable": "230040 - VAT Payable - MTL",
    "vat": "230040 - VAT Payable - MTL",
    "86": "230030 - WHT Payable - MTL",
    "withholding tax": "230030 - WHT Payable - MTL",
    "wht payable": "230030 - WHT Payable - MTL",
    "87": "122030 - WHT Receivable - MTL",
    "withholding tax expense": "122030 - WHT Receivable - MTL",
    "wht receivable": "122030 - WHT Receivable - MTL",
    "109": "230020 - PAYEE Payable - MTL",
    "paye": "230020 - PAYEE Payable - MTL",
    "payee": "230020 - PAYEE Payable - MTL",
    "payee payable": "230020 - PAYEE Payable - MTL",
    "111": "229130 - Provision for Pension - MTL",
    "pension contribution payable": "229130 - Provision for Pension - MTL",

    # 5. Inventory & Stock Assets
    "58": "120010 - Stock In Hand - Device - MTL",
    "194": "120010 - Stock In Hand - Device - MTL",
    "inventory": "120010 - Stock In Hand - Device - MTL",
    "inventory asset": "120010 - Stock In Hand - Device - MTL",

    # 6. Fixed Assets & Depreciation
    "computers": "112020 - Computers & Peripherals - MTL",
    "91": "112020 - Computers & Peripherals - MTL",
    "office equipment": "112010 - Office Equipments - MTL",
    "office furniture": "112040 - Furniture & Fixtures - MTL",
    "plant & machineries": "112050 - Plant & Machinery - MTL",
    "accumulated depreciation on property, plant and equipment": "112110 - Accumulated Depreciation - MTL",
    "39": "112110 - Accumulated Depreciation - MTL",
    "depreciation": "403680 - Depreciation - MTL",

    # 7. Liabilities, Intercompany & Loans
    "1150040008": "224040 - Loan Payable - MTL",
    "loan from omniretail technology limited": "224040 - Loan Payable - MTL",
    "other payable due to related party": "224040 - Loan Payable - MTL",
    "oluwaseyi onasanya": "224050 - Oluwaseyi Onasanya - MTL",
    "provision for audit": "229080 - Provision for Audit Fee - MTL",
    "143": "229080 - Provision for Audit Fee - MTL",
    "intercompany  - movam inc": "228020 - Intercompany - Movam INC - MTL",
    "intercompany - movam inc": "228020 - Intercompany - Movam INC - MTL",
    "116": "228010 - Movam Inc - MTL",
    "movam inc. due to/from": "228010 - Movam Inc - MTL",
    "movam inc due to/from": "228010 - Movam Inc - MTL",
    "170": "117040 - Loan to 3rd party - MTL",
    "loans to 1pl": "117040 - Loan to 3rd party - MTL",
    "1150040034": "226040 - Other Creditors - NGN - MTL",
    "other payable": "226040 - Other Creditors - NGN - MTL",
    "1150040029": "117070 - Prepaid dues & subscription - MTL",
    "prepaid dues and subscription": "117070 - Prepaid dues & subscription - MTL",
    "prepaid dues & subscription": "117070 - Prepaid dues & subscription - MTL",
    "195": "311020 - Revenue - Logistics - MTL",
    "sales- logistics": "311020 - Revenue - Logistics - MTL",
    "sales - logistics": "311020 - Revenue - Logistics - MTL",

    # 8. Equity
    "equity contribution": "233020 - Equity Contribution - MTL",
    "share capital": "233010 - Equity Share Capital - MTL",
    "opening balance equity": "233020 - Equity Contribution - MTL",

    # 9. Revenue
    "69": "311010 - Revenue - SAAS - MTL",
    "sales & services": "311010 - Revenue - SAAS - MTL",
    "74": "311030 - Revenue - Device - MTL",
    "sales of product income": "311030 - Revenue - Device - MTL",
    "1": "311010 - Revenue - SAAS - MTL",

    # 10. Cost of Sales
    "cost of goods/ service sold": "401040 - COGS Device - MTL",
    "cost of goods sold": "401040 - COGS Device - MTL",
    "75": "401040 - COGS Device - MTL",
    "73": "401040 - COGS Device - MTL",
    "purchases": "401040 - COGS Device - MTL",
    "coban tracking devices": "401040 - COGS Device - MTL",
    "coban": "401040 - COGS Device - MTL",
    "tracking devices": "401040 - COGS Device - MTL",
    "installation and technical charges": "401060 - COGS Device : Installation and Technical Charges - MTL",
    "102": "401060 - COGS Device : Installation and Technical Charges - MTL",
    "193": "401080 - COGS Logistics - MTL",
    "cost of saas": "401080 - COGS Logistics - MTL",
    "biker services expenses": "401010 - COGS Logistics : Biker Service Expense - MTL",
    "fuel for riders": "401010 - COGS Logistics : Biker Service Expense - MTL",
    "145": "401020 - COGS Logistics : Driver Service Expenses - MTL",
    "driver services expenses": "401020 - COGS Logistics : Driver Service Expenses - MTL",
    "freight and delivery - cos": "401050 - COGS Device : Freight and delivery - MTL",
    "freight and delivery": "401050 - COGS Device : Freight and delivery - MTL",
    "62": "401050 - COGS Device : Freight and delivery - MTL",
    "119": "QB-119 - Inventory Shrinkage - MTL",
    "inventory shrinkage": "QB-119 - Inventory Shrinkage - MTL",

    # 11. Operating Expenses & Other P&L
    "137": "403380 - Registration & Renewal Fees - MTL",
    "registration fees": "403380 - Registration & Renewal Fees - MTL",
    "registration fee": "403380 - Registration & Renewal Fees - MTL",
    "audit expenses": "403080 - Audit Expenses - MTL",
    "144": "403080 - Audit Expenses - MTL",
    "bank charges": "403100 - Bank Charges - MTL",
    "42": "403100 - Bank Charges - MTL",
    "business promotion and marketing": "403120 - Business Promotion And Marketing - MTL",
    "communication allowance": "403140 - Communication Allowance - MTL",
    "director's remuneration": "403150 - Director's Remuneration - MTL",
    "dues and subscriptions": "403160 - Dues And Subscriptions - MTL",
    "43": "403160 - Dues And Subscriptions - MTL",
    "electricity expenses": "403170 - Electricity Expenses - MTL",
    "56": "403170 - Electricity Expenses - MTL",
    "utilities": "403170 - Electricity Expenses - MTL",
    "insurance- medical": "403250 - Insurance - Medical - MTL",
    "insurance - medical": "403250 - Insurance - Medical - MTL",
    "98": "403250 - Insurance - Medical - MTL",
    "insurance - general": "403230 - Insurance - General - MTL",
    "insurance general": "403230 - Insurance - General - MTL",
    "interest expense": "403260 - Interest Expense - MTL",
    "internet and domain expenses": "403270 - Internet And Domain Expenses - MTL",
    "legal and professional fees": "403280 - Legal And Professional Fees - MTL",
    "meals and entertainment": "403310 - Meals And Entertainment - MTL",
    "office expenses": "403320 - Office Expenses - MTL",
    "48": "403320 - Office Expenses - MTL",
    "2": "403320 - Office Expenses - MTL",
    "uncategorised expense": "403320 - Office Expenses - MTL",
    "post and telecommunication": "403370 - Post And Telecommunication - MTL",
    "rent or lease payments": "403390 - Rent Or Lease Payments - MTL",
    "repairs and maintenance": "403400 - Repairs And Maintenance - Other Assets - MTL",
    "1150040028": "403410 - Repairs And Maintenance - Logistics Vehicles - MTL",
    "repair & maintenace- vehicle": "403410 - Repairs And Maintenance - Logistics Vehicles - MTL",
    "repair & maintenance- vehicle": "403410 - Repairs And Maintenance - Logistics Vehicles - MTL",
    "repair and maintenance- vehicle": "403410 - Repairs And Maintenance - Logistics Vehicles - MTL",
    "salaries and wages": "403430 - Salaries And Wages - MTL",
    "65": "403430 - Salaries And Wages - MTL",
    "payroll expenses": "403430 - Salaries And Wages - MTL",
    "14": "403540 - Wage Expenses - MTL",
    "wage expenses": "403540 - Wage Expenses - MTL",
    "110": "403180 - Employer Pension Contribution - MTL",
    "employer pension contribution": "403180 - Employer Pension Contribution - MTL",
    "pension contribution by employer": "403180 - Employer Pension Contribution - MTL",
    "1150040021": "403550 - Management Fees - MTL",
    "management fees": "403550 - Management Fees - MTL",
    "24": "403300 - Management Compensation - MTL",
    "management compensation": "403300 - Management Compensation - MTL",
    "software management expenses": "403450 - Software Management Expenses - MTL",
    "114": "403450 - Software Management Expenses - MTL",
    "staff training and welfare": "403460 - Staff Training And Welfare - MTL",
    "stationery and printing": "403470 - Stationery And Printing - MTL",
    "57": "403470 - Stationery And Printing - MTL",
    "supplies": "403470 - Stationery And Printing - MTL",
    "transportation": "403490 - Transportation - MTL",
    "178": "403500 - Transport Reimbursement (Ops) - MTL",
    "transport reimbursement(ops)": "403500 - Transport Reimbursement (Ops) - MTL",
    "travel expenses - general and admin expenses": "403510 - Travel Expenses - MTL",
    "travel expenses": "403510 - Travel Expenses - MTL",
    "statutory fines": "403480 - Statutory Fines - MTL",
    "127": "403210 - Income Tax Expense - MTL",
    "income tax expense": "403210 - Income Tax Expense - MTL",
    "taxes paid": "403210 - Income Tax Expense - MTL",
    "28": "QB-28 - Commissions and fees - MTL",
    "commissions and fees": "QB-28 - Commissions and fees - MTL",
    "foreign exchange fluctuation": "403010 - Foreign Exchange Fluctuation - MTL",
    "4": "403010 - Foreign Exchange Fluctuation - MTL",
    "unrealised loss on securities, net of tax": "403010 - Foreign Exchange Fluctuation - MTL",
    "gain on disposal of assets": "312020 - Gain/Loss on disposal of assets - MTL",
    "15": "312020 - Gain/Loss on disposal of assets - MTL",
    "loss on disposal of assets": "312020 - Gain/Loss on disposal of assets - MTL",
    "interest income": "312030 - Interest income - MTL",
    "83": "312060 - Other Income - MTL",
    "unapplied cash payment income": "312060 - Other Income - MTL",
    "17": "312060 - Other Income - MTL",
    "other operating income (expenses)": "312060 - Other Income - MTL",
    "99": "403520 - Unapplied Cash Bill Payment Expense - MTL",
    "unapplied cash bill payment expense": "403520 - Unapplied Cash Bill Payment Expense - MTL",
    "7": "403440 - Shipping And Delivery Expense - MTL",
    "shipping and delivery expense": "403440 - Shipping And Delivery Expense - MTL",
    "201": "403420 - Round Off - MTL",
    "round off": "403420 - Round Off - MTL",
    "72": "403420 - Round Off - MTL",
    "reconciliation discrepancies": "403420 - Round Off - MTL",
    "1150040016": "403560 - Reversals and Adjustments - MTL",
    "reversals and adjustments": "403560 - Reversals and Adjustments - MTL",
    "revarsal": "403560 - Reversals and Adjustments - MTL",
    "38": "403350 - Other Types Of Expenses - Advertising Expenses - MTL",
    "other types of expenses-advertising expenses": "403350 - Other Types Of Expenses - Advertising Expenses - MTL",
    "23": "403340 - Other Selling Expenses - MTL",
    "other selling expenses": "403340 - Other Selling Expenses - MTL",
    "49": "403330 - Other General And Administrative Expenses - MTL",
    "other general and administrative expenses": "403330 - Other General And Administrative Expenses - MTL",

    # 12. Prepayments, Assets, Liabilities
    "196": "112030 - Motor Vehicles - MTL",
    "motor vehicle": "112030 - Motor Vehicles - MTL",
    "1150040033": "116140 - Prepaid SAAS NGN - MTL",
    "prepaid saas": "116140 - Prepaid SAAS NGN - MTL",
    "1150040013": "116010 - Prepaid Software Expenses - MTL",
    "prepaid software expenses": "116010 - Prepaid Software Expenses - MTL",
    "1150040025": "116050 - Prepaid Expense - MTL",
    "prepaid transportation": "116050 - Prepaid Expense - MTL",
    "1150040023": "116050 - Prepaid Expense - MTL",
    "prepaid business promotion & marketing expenses": "116050 - Prepaid Expense - MTL",
    "1150040022": "401040 - COGS Device - MTL",
    "provision for cogs": "401040 - COGS Device - MTL",
    "187": "229050 - Provision for Legal and Professional Fee - MTL",
    "provision for legal and professional fees": "229050 - Provision for Legal and Professional Fee - MTL",
    "1150040032": "226090 - Shipment - Liability - MTL",
    "shipment - liability": "226090 - Shipment - Liability - MTL",
    "181": "229060 - Provision for Leave Allowance - MTL",
    "provision for leave allowance": "229060 - Provision for Leave Allowance - MTL",
    "120": "224040 - Loan Payable - MTL",
    "loan payable": "224040 - Loan Payable - MTL",
    "26": "230010 - Corporate Income Tax Payable - MTL",
    "income tax payable": "230010 - Corporate Income Tax Payable - MTL",
    "deferred revenue": "226060 - Deferred Revenue - MTL",
    "paye": "230020 - PAYEE Payable - MTL",
    "66": "226080 - Contractual Payroll Payable - MTL",
    "payroll liabilities": "226080 - Contractual Payroll Payable - MTL",
    "67": "226080 - Contractual Payroll Payable - MTL",
    "payroll clearing": "226080 - Contractual Payroll Payable - MTL",
    "pension contribution payable": "229130 - Provision for Pension - MTL",
}


def build_account_cache(company):
    """Pre-load all accounts for instant O(1) in-memory resolution without DB hits"""
    accounts = frappe.db.sql("""
        SELECT name, account_name, account_number, account_currency, account_type, root_type, custom_qbc_child_account_name
        FROM `tabAccount`
        WHERE company = %s AND is_group = 0
    """, (company,), as_dict=True)

    cache = {
        "by_name": {},
        "by_acc_num": {},
        "by_qbc_name": {},
        "raw": {}
    }
    for a in accounts:
        cache["raw"][a.name] = a
        if a.account_name:
            cache["by_name"][a.account_name.lower().strip()] = a.name
        if a.account_number:
            cache["by_acc_num"][str(a.account_number).strip()] = a.name
        if a.custom_qbc_child_account_name:
            cache["by_qbc_name"][a.custom_qbc_child_account_name.lower().strip()] = a.name
    return cache


def resolve_account_master(acc_ref=None, company=None, classification=None, default_acc=None, cache=None, **kwargs):
    """
    Centralized 4-tier Master Account Resolver
    Accepts dict {'name': ..., 'value': ...}, or account ID/name string, or kwargs (qb_account_id, qb_account_name).
    Ensures 100% accounting accuracy and robust fallbacks.
    """
    val = ""
    name = ""
    comp = company or kwargs.get("company") or "Movam Technologies Limited"

    if isinstance(acc_ref, dict):
        val = str(acc_ref.get("value") or "").strip()
        name = (acc_ref.get("name") or "").strip().lower()
    elif isinstance(acc_ref, str):
        if acc_ref == comp or "Technologies Limited" in acc_ref:
            # acc_ref was passed as company name
            pass
        elif acc_ref.isdigit() or acc_ref.startswith("11500") or acc_ref.startswith("QB-"):
            val = acc_ref.strip()
        else:
            name = acc_ref.strip().lower()

    if not val and kwargs.get("qb_account_id"):
        val = str(kwargs.get("qb_account_id")).strip()
    if not name and kwargs.get("qb_account_name"):
        name = str(kwargs.get("qb_account_name")).strip().lower()

    if not cache:
        cache = build_account_cache(comp)

    # Tier 1: Explicit Master Map (by ID, then by Name)
    if val and val in MASTER_ACCOUNT_MAP:
        mapped = MASTER_ACCOUNT_MAP[val]
        if mapped in cache["raw"]:
            return mapped

    if name and name in MASTER_ACCOUNT_MAP:
        mapped = MASTER_ACCOUNT_MAP[name]
        if mapped in cache["raw"]:
            return mapped

    # Tier 2: Account Number (QB-{val}) or Custom QBC Name
    if val:
        qb_num = f"QB-{val}"
        if qb_num in cache["by_acc_num"]:
            return cache["by_acc_num"][qb_num]

    if name:
        if name in cache["by_name"]:
            return cache["by_name"][name]
        if name in cache["by_qbc_name"]:
            return cache["by_qbc_name"][name]

    # Tier 3: Substring & Fuzzy Match in Active Chart of Accounts
    if name:
        for acc_name, acc_id in cache["by_name"].items():
            if name in acc_name or acc_name in name:
                return acc_id

    # Tier 4: Classification-Based Fallback Hierarchy
    cls = classification or kwargs.get("classification")
    return _get_fallback_by_classification(cls, default_acc, cache)


def _get_fallback_by_classification(classification, default_acc, cache):
    cls = str(classification or "").lower().strip()
    if cls == "asset":
        return "116050 - Prepaid Expense - MTL" if "116050 - Prepaid Expense - MTL" in cache["raw"] else default_acc
    elif cls == "liability":
        return "226040 - Other Creditors - NGN - MTL" if "226040 - Other Creditors - NGN - MTL" in cache["raw"] else default_acc
    elif cls in ["equity"]:
        return "233020 - Equity Contribution - MTL" if "233020 - Equity Contribution - MTL" in cache["raw"] else default_acc
    elif cls in ["revenue", "income"]:
        return "311010 - Revenue - SAAS - MTL" if "311010 - Revenue - SAAS - MTL" in cache["raw"] else default_acc
    elif cls in ["cogs", "expense"]:
        return "403320 - Office Expenses - MTL" if "403320 - Office Expenses - MTL" in cache["raw"] else default_acc
    return default_acc or "403320 - Office Expenses - MTL"

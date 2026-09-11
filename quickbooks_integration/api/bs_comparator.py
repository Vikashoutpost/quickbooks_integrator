import frappe
from frappe.utils import flt

# Audited QuickBooks Balance Sheet benchmarks extracted directly from QuickBooks API reports/BalanceSheet
QBO_AUDITED_BS = {
    "2022": {
        "assets": 13332088.82,
        "current_assets": 5496591.48,
        "long_term_assets": 7835497.34,
        "liabilities": 14263982.03,
        "current_liabilities": 14263982.03,
        "non_current_liabilities": 0.00,
        "equity": -931893.21,
        "total_liab_equity": 13332088.82,
        "details": {
            "Bank & Cash Accounts": {"category": "Current Assets", "qbo": 1006931.63, "accounts": ["119010 - FCMB Bank - MTL", "119020 - Globus Bank - MTL", "119040 - Petty Cash - MTL"]},
            "Accounts Receivable (A/R)": {"category": "Current Assets", "qbo": 673625.00, "accounts": ["121010 - Trade Receivables - NGN - MTL"]},
            "Prepaid Expenses": {"category": "Current Assets", "qbo": 3816034.85, "accounts": ["116050 - Prepaid Expense - MTL"]},
            "Fixed Assets (Net of Depr.)": {"category": "Fixed Assets", "qbo": 7835497.34, "accounts": ["112010 - Office Equipments - MTL", "112020 - Computers & Peripherals - MTL", "112030 - Motor Vehicles - MTL", "112040 - Furniture & Fixtures - MTL", "112050 - Plant & Machinery - MTL", "112110 - Accumulated Depreciation - MTL"]},
            "Accounts Payable (A/P)": {"category": "Current Liabilities", "qbo": 8565415.82, "accounts": ["225010 - Trade Creditors - NGN - MTL"]},
            "PAYE & Pension Payable": {"category": "Current Liabilities", "qbo": 5698566.21, "accounts": ["230020 - PAYEE Payable - MTL", "229130 - Provision for Pension - MTL"]},
            "Share Capital": {"category": "Equity", "qbo": 10000000.00, "accounts": ["233010 - Equity Share Capital - MTL"]},
            "Equity Contribution": {"category": "Equity", "qbo": 65788583.75, "accounts": ["233020 - Equity Contribution - MTL"]},
            "Cumulative Retained Earnings": {"category": "Equity", "qbo": -76720476.96, "is_pl": True},
        }
    },
    "2023": {
        "assets": 44994775.27,
        "current_assets": 37694041.80,
        "long_term_assets": 7300733.47,
        "liabilities": 103788459.91,
        "current_liabilities": 94637317.50,
        "non_current_liabilities": 9151142.41,
        "equity": -58793684.64,
        "total_liab_equity": 44994775.27,
        "details": {
            "FCMB Bank": {"category": "Current Assets", "qbo": 14163.48, "accounts": ["119010 - FCMB Bank - MTL"]},
            "Globus Bank": {"category": "Current Assets", "qbo": 7564620.40, "accounts": ["119020 - Globus Bank - MTL"]},
            "Petty Cash": {"category": "Current Assets", "qbo": 65622.35, "accounts": ["119040 - Petty Cash - MTL"]},
            "Accounts Receivable (A/R)": {"category": "Current Assets", "qbo": 18888987.05, "accounts": ["121010 - Trade Receivables - NGN - MTL"]},
            "Inventory": {"category": "Current Assets", "qbo": 2037737.50, "accounts": ["120010 - Stock In Hand - Device - MTL"]},
            "Prepaid Expenses": {"category": "Current Assets", "qbo": 3816034.85, "accounts": ["116050 - Prepaid Expense - MTL"]},
            "Staff Salary Advance": {"category": "Current Assets", "qbo": 177500.00, "accounts": ["117020 - Staff Salary Advance - MTL"]},
            "WHT Receivable": {"category": "Current Assets", "qbo": 5129376.01, "accounts": ["122030 - WHT Receivable - MTL"]},
            "Fixed Assets (Net of Depr.)": {"category": "Fixed Assets", "qbo": 7300733.47, "accounts": ["112010 - Office Equipments - MTL", "112020 - Computers & Peripherals - MTL", "112040 - Furniture & Fixtures - MTL", "112050 - Plant & Machinery - MTL", "112110 - Accumulated Depreciation - MTL"]},
            "Accounts Payable (A/P)": {"category": "Current Liabilities", "qbo": 45411242.52, "accounts": ["225010 - Trade Creditors - NGN - MTL", "225020 - Trade Creditors - USD - MTL"]},
            "Deferred Revenue": {"category": "Current Liabilities", "qbo": 3948738.00, "accounts": ["226060 - Deferred Revenue - MTL"]},
            "PAYE Payable": {"category": "Current Liabilities", "qbo": 2021972.47, "accounts": ["230020 - PAYEE Payable - MTL"]},
            "Pension Contribution Payable": {"category": "Current Liabilities", "qbo": 8728046.98, "accounts": ["229130 - Provision for Pension - MTL"]},
            "VAT Control": {"category": "Current Liabilities", "qbo": 2101366.95, "accounts": ["230040 - VAT Payable - MTL"]},
            "Withholding Tax": {"category": "Current Liabilities", "qbo": 328814.58, "accounts": ["230030 - WHT Payable - MTL"]},
            "Related Party Loans": {"category": "Current Liabilities", "qbo": 32097136.00, "accounts": ["224040 - Loan Payable - MTL"]},
            "Movam Inc. (Intercompany)": {"category": "Non-Current Liabilities", "qbo": 9151142.41, "accounts": ["228010 - Movam Inc - MTL"]},
            "Share Capital": {"category": "Equity", "qbo": 10000000.00, "accounts": ["233010 - Equity Share Capital - MTL"]},
            "Equity Contribution": {"category": "Equity", "qbo": 84738583.75, "accounts": ["233020 - Equity Contribution - MTL"]},
            "Cumulative Retained Earnings": {"category": "Equity", "qbo": -153682268.39, "is_pl": True},
        }
    },
    "2024": {
        "assets": 160208899.86,
        "current_assets": 142798799.06,
        "long_term_assets": 17410100.80,
        "liabilities": 168707977.11,
        "current_liabilities": 135730863.38,
        "non_current_liabilities": 32977113.73,
        "equity": -8499077.25,
        "total_liab_equity": 160208899.86,
        "details": {
            "Bank & Cash Accounts": {"category": "Current Assets", "qbo": 8230482.75, "accounts": ["119010 - FCMB Bank - MTL", "119020 - Globus Bank - MTL", "119030 - Globus Bank - 8000006697 - MTL", "119040 - Petty Cash - MTL", "119050 - Globus Bank USD - 5000032967 - MTL", "119060 - Globus Bank USD - 8000006697 - MTL"]},
            "Accounts Receivable (NGN & USD)": {"category": "Current Assets", "qbo": 87647662.40, "accounts": ["121010 - Trade Receivables - NGN - MTL", "121020 - Trade Receivables - USD - MTL"]},
            "Inventory (Net)": {"category": "Current Assets", "qbo": 13017099.50, "accounts": ["120010 - Stock In Hand - Device - MTL"]},
            "Prepaid Expenses": {"category": "Current Assets", "qbo": 5763934.10, "accounts": ["116050 - Prepaid Expense - MTL", "117070 - Prepaid dues & subscription - MTL"]},
            "Staff Salary Advance": {"category": "Current Assets", "qbo": -138579.67, "accounts": ["117020 - Staff Salary Advance - MTL"]},
            "WHT Receivable": {"category": "Current Assets", "qbo": 27153743.98, "accounts": ["122030 - WHT Receivable - MTL"]},
            "Loans to 1PL": {"category": "Current Assets", "qbo": 1124456.00, "accounts": ["118010 - Loans to 1PL - MTL", "117040 - Loan to 3rd party - MTL"]},
            "Fixed Assets (Net of Depr.)": {"category": "Fixed Assets", "qbo": 17410100.80, "accounts": ["112010 - Office Equipments - MTL", "112020 - Computers & Peripherals - MTL", "112030 - Motor Vehicles - MTL", "112040 - Furniture & Fixtures - MTL", "112050 - Plant & Machinery - MTL", "112110 - Accumulated Depreciation - MTL"]},
            "Accounts Payable (NGN & USD)": {"category": "Current Liabilities", "qbo": 40371469.00, "accounts": ["225010 - Trade Creditors - NGN - MTL", "225020 - Trade Creditors - USD - MTL"]},
            "Related Party Loans": {"category": "Current Liabilities", "qbo": 38085306.02, "accounts": ["224040 - Loan Payable - MTL"]},
            "PAYE & Pension Payable": {"category": "Current Liabilities", "qbo": 28979414.38, "accounts": ["230020 - PAYEE Payable - MTL", "229130 - Provision for Pension - MTL"]},
            "VAT Control": {"category": "Current Liabilities", "qbo": 7207700.32, "accounts": ["230040 - VAT Payable - MTL"]},
            "Corporate Income Tax Payable": {"category": "Current Liabilities", "qbo": 1884538.00, "accounts": ["230010 - Corporate Income Tax Payable - MTL"]},
            "Withholding Tax": {"category": "Current Liabilities", "qbo": 90727.15, "accounts": ["230030 - WHT Payable - MTL"]},
            "Other Payables & Accruals": {"category": "Current Liabilities", "qbo": 18861708.51, "accounts": ["224050 - Other Payable - MTL", "226040 - Other Creditors - NGN - MTL", "229050 - Provision for Legal and Professional Fee - MTL", "229060 - Provision for Leave Allowance - MTL", "229070 - Provision for Employee Bonus - MTL", "229100 - Provision For Statutory Fines - MTL", "QB-197 - accrued Software Management Account - MTL"]},
            "Movam Inc. (Intercompany)": {"category": "Non-Current Liabilities", "qbo": 32977113.73, "accounts": ["228010 - Movam Inc - MTL"]},
            "Share Capital": {"category": "Equity", "qbo": 10000000.00, "accounts": ["233010 - Equity Share Capital - MTL"]},
            "Equity Contribution": {"category": "Equity", "qbo": 84738583.75, "accounts": ["233020 - Equity Contribution - MTL"]},
            "Cumulative Retained Earnings": {"category": "Equity", "qbo": -107182815.98, "is_pl": True},
        }
    },
    "2025": {
        "assets": 437046598.40,
        "current_assets": 163649801.37,
        "long_term_assets": 273396797.03,
        "liabilities": 492312640.35,
        "current_liabilities": 213386049.87,
        "non_current_liabilities": 278926590.48,
        "equity": -55266041.95,
        "total_liab_equity": 437046598.40,
        "details": {
            "FCMB Bank": {"category": "Current Assets", "qbo": 17042829.30, "accounts": ["119010 - FCMB Bank - MTL"]},
            "Petty Cash": {"category": "Current Assets", "qbo": -16331.04, "accounts": ["119040 - Petty Cash - MTL"]},
            "Globus Accounts (NGN & USD)": {"category": "Current Assets", "qbo": 5655986.36, "accounts": ["119020 - Globus Bank - MTL", "119050 - Globus Bank USD - 5000032967 - MTL", "119060 - Globus Bank USD - 8000006697 - MTL"]},
            "Accounts Receivable (NGN & USD)": {"category": "Current Assets", "qbo": 84480543.41, "accounts": ["121010 - Trade Receivables - NGN - MTL", "121020 - Trade Receivables - USD - MTL"]},
            "Inventory Asset": {"category": "Current Assets", "qbo": 81162.50, "accounts": ["120010 - Stock In Hand - Device - MTL"]},
            "Total Prepayments (Combined)": {"category": "Current Assets", "qbo": 21873595.13, "accounts": ["116010 - Prepaid Software Expenses - MTL", "116030 - Prepaid Registration Fees - MTL", "116050 - Prepaid Expense - MTL", "116140 - Prepaid SAAS NGN - MTL", "117070 - Prepaid dues & subscription - MTL"]},
            "Staff Salary Advance": {"category": "Current Assets", "qbo": 77420.33, "accounts": ["117020 - Staff Salary Advance - MTL"]},
            "WHT Receivable": {"category": "Current Assets", "qbo": 34454595.38, "accounts": ["122030 - WHT Receivable - MTL"]},
            "Fixed Assets: Property, Plant & Equipment": {"category": "Fixed Assets", "qbo": 294702673.25, "accounts": ["112010 - Office Equipments - MTL", "112020 - Computers & Peripherals - MTL", "112030 - Motor Vehicles - MTL", "112040 - Furniture & Fixtures - MTL", "112050 - Plant & Machinery - MTL"]},
            "Accumulated Depreciation": {"category": "Fixed Assets", "qbo": -21305876.22, "accounts": ["112110 - Accumulated Depreciation - MTL"]},
            "Net Fixed Assets (Total)": {"category": "Fixed Assets", "qbo": 273396797.03, "accounts": ["112010 - Office Equipments - MTL", "112020 - Computers & Peripherals - MTL", "112030 - Motor Vehicles - MTL", "112040 - Furniture & Fixtures - MTL", "112050 - Plant & Machinery - MTL", "112110 - Accumulated Depreciation - MTL"]},
            "Accounts Payable (NGN & USD)": {"category": "Current Liabilities", "qbo": 43498922.60, "accounts": ["225010 - Trade Creditors - NGN - MTL", "225020 - Trade Creditors - USD - MTL", "229080 - Provision for Audit Fee - MTL"]},
            "OmniRetail Loan & Payables": {"category": "Non-Current Liabilities", "qbo": 316009261.02, "accounts": ["224040 - Loan Payable - MTL", "224010 - OmniRetail Technology Limited (Payables) - MTL"]},
            "Intercompany Movam INC": {"category": "Non-Current Liabilities", "qbo": 61581113.73, "accounts": ["228020 - Intercompany - Movam INC - MTL"]},
            "PAYE Payable": {"category": "Current Liabilities", "qbo": 1736866.56, "accounts": ["230020 - PAYEE Payable - MTL"]},
            "Pension Contribution Payable": {"category": "Current Liabilities", "qbo": 36330881.19, "accounts": ["229130 - Provision for Pension - MTL"]},
            "Corporate Income Tax Payable": {"category": "Current Liabilities", "qbo": 1884538.00, "accounts": ["230010 - Corporate Income Tax Payable - MTL"]},
            "Withholding Tax": {"category": "Current Liabilities", "qbo": 385055.85, "accounts": ["230030 - WHT Payable - MTL"]},
            "VAT Control": {"category": "Current Liabilities", "qbo": 3722578.65, "accounts": ["230040 - VAT Payable - MTL"]},
            "Other Payables & Accruals": {"category": "Current Liabilities", "qbo": 27163422.75, "accounts": ["224050 - Other Payable - MTL", "226040 - Other Creditors - NGN - MTL", "226090 - Shipment - Liability - MTL", "229050 - Provision for Legal and Professional Fee - MTL", "229060 - Provision for Leave Allowance - MTL", "229070 - Provision for Employee Bonus - MTL", "229090 - Provision For COGS - Logistics - MTL", "229100 - Provision For Statutory Fines - MTL"]},
            "Share Capital": {"category": "Equity", "qbo": 10000000.00, "accounts": ["233010 - Equity Share Capital - MTL"]},
            "Equity Contribution": {"category": "Equity", "qbo": 84738583.75, "accounts": ["233020 - Equity Contribution - MTL"]},
            "Cumulative Retained Earnings": {"category": "Equity", "qbo": -153949780.68, "is_pl": True},
        }
    }
}


def get_live_erp_bs(as_of_date):
    """
    Computes ERPNext cumulative balances as of date for QuickBooks cost center.
    """
    gl_entries = frappe.db.sql("""
        SELECT a.root_type, a.name as account, a.account_name,
               SUM(gl.debit - gl.credit) as net_debit,
               SUM(gl.credit - gl.debit) as net_credit
        FROM `tabGL Entry` gl
        JOIN `tabAccount` a ON gl.account = a.name
        WHERE gl.posting_date <= %s
          AND gl.is_cancelled = 0
          AND gl.cost_center LIKE 'QuickBooks%%'
        GROUP BY a.name
    """, (as_of_date,), as_dict=True)

    accounts = {r["account"]: r for r in gl_entries}

    total_assets = sum(r["net_debit"] for r in gl_entries if r["root_type"] == "Asset")
    total_liabilities = sum(r["net_credit"] for r in gl_entries if r["root_type"] == "Liability")
    equity_base = sum(r["net_credit"] for r in gl_entries if r["root_type"] == "Equity")

    cum_income = sum(r["net_credit"] for r in gl_entries if r["root_type"] == "Income")
    cum_expense = sum(r["net_debit"] for r in gl_entries if r["root_type"] == "Expense")
    cum_pl = round(cum_income - cum_expense, 2)

    total_equity = round(equity_base + cum_pl, 2)
    total_liab_equity = round(total_liabilities + total_equity, 2)

    return {
        "assets": round(total_assets, 2),
        "liabilities": round(total_liabilities, 2),
        "equity": total_equity,
        "cum_pl": cum_pl,
        "total_liab_equity": total_liab_equity,
        "accounts": accounts
    }


def calc_match(erp_val, qbo_val):
    if abs(qbo_val) < 0.01:
        return 100.0 if abs(erp_val) < 0.01 else 0.0
    diff = abs(erp_val - qbo_val)
    pct = round((1.0 - (diff / abs(qbo_val))) * 100.0, 2)
    return max(0.0, min(100.0, pct))


@frappe.whitelist()
def get_bs_comparison(year="all_years"):
    target_year = "2025" if year in ["all_years", ""] else str(year)
    as_of_date = f"{target_year}-12-31"

    erp = get_live_erp_bs(as_of_date)
    qbo = QBO_AUDITED_BS.get(target_year, QBO_AUDITED_BS["2025"])

    summary = {
        "year": target_year,
        "as_of_date": as_of_date,
        "qbo_assets": qbo["assets"],
        "erp_assets": erp["assets"],
        "assets_diff": round(erp["assets"] - qbo["assets"], 2),
        "assets_match_pct": calc_match(erp["assets"], qbo["assets"]),

        "qbo_liabilities": qbo["liabilities"],
        "erp_liabilities": erp["liabilities"],
        "liabilities_diff": round(erp["liabilities"] - qbo["liabilities"], 2),
        "liabilities_match_pct": calc_match(erp["liabilities"], qbo["liabilities"]),

        "qbo_equity": qbo["equity"],
        "erp_equity": erp["equity"],
        "equity_diff": round(erp["equity"] - qbo["equity"], 2),
        "equity_match_pct": calc_match(erp["equity"], qbo["equity"]),

        "qbo_total_liab_equity": qbo["total_liab_equity"],
        "erp_total_liab_equity": erp["total_liab_equity"],
        "tle_diff": round(erp["total_liab_equity"] - qbo["total_liab_equity"], 2),
        "tle_match_pct": calc_match(erp["total_liab_equity"], qbo["total_liab_equity"]),
    }

    top_categories = [
        {"name": "Total Assets", "qbo": summary["qbo_assets"], "erp": summary["erp_assets"], "diff": summary["assets_diff"], "match_pct": summary["assets_match_pct"]},
        {"name": "Total Liabilities", "qbo": summary["qbo_liabilities"], "erp": summary["erp_liabilities"], "diff": summary["liabilities_diff"], "match_pct": summary["liabilities_match_pct"]},
        {"name": "Total Shareholders' Equity", "qbo": summary["qbo_equity"], "erp": summary["erp_equity"], "diff": summary["equity_diff"], "match_pct": summary["equity_match_pct"]},
        {"name": "Total Liabilities & Equity", "qbo": summary["qbo_total_liab_equity"], "erp": summary["erp_total_liab_equity"], "diff": summary["tle_diff"], "match_pct": summary["tle_match_pct"]},
    ]

    all_years = []
    for y in ["2022", "2023", "2024", "2025"]:
        y_erp = get_live_erp_bs(f"{y}-12-31")
        y_qbo = QBO_AUDITED_BS[y]
        all_years.append({
            "year": y,
            "qbo_assets": y_qbo["assets"],
            "erp_assets": y_erp["assets"],
            "assets_diff": round(y_erp["assets"] - y_qbo["assets"], 2),
            "assets_match": calc_match(y_erp["assets"], y_qbo["assets"]),

            "qbo_liab": y_qbo["liabilities"],
            "erp_liab": y_erp["liabilities"],
            "liab_diff": round(y_erp["liabilities"] - y_qbo["liabilities"], 2),
            "liab_match": calc_match(y_erp["liabilities"], y_qbo["liabilities"]),

            "qbo_equity": y_qbo["equity"],
            "erp_equity": y_erp["equity"],
            "equity_diff": round(y_erp["equity"] - y_qbo["equity"], 2),
            "equity_match": calc_match(y_erp["equity"], y_qbo["equity"]),

            "qbo_tle": y_qbo["total_liab_equity"],
            "erp_tle": y_erp["total_liab_equity"],
            "tle_diff": round(y_erp["total_liab_equity"] - y_qbo["total_liab_equity"], 2),
            "tle_match": calc_match(y_erp["total_liab_equity"], y_qbo["total_liab_equity"]),
        })

    # Account-level detail rows
    detail_rows = []
    erp_accounts = erp["accounts"]
    qbo_details = qbo.get("details", {})

    for item_name, info in qbo_details.items():
        q_val = info["qbo"]
        cat = info["category"]
        is_pl = info.get("is_pl", False)

        if is_pl:
            e_val = erp["cum_pl"]
            e_name = "Cumulative P&L (Retained Earnings)"
        else:
            acc_list = info.get("accounts", [])
            e_val = 0.0
            matched_names = []
            for a in acc_list:
                if a in erp_accounts:
                    matched_names.append(a)
                    # Asset net debit, Liability/Equity net credit
                    if cat in ["Current Assets", "Fixed Assets"]:
                        e_val += erp_accounts[a]["net_debit"]
                    else:
                        e_val += erp_accounts[a]["net_credit"]
            e_name = ", ".join(matched_names) if matched_names else (acc_list[0] if acc_list else "—")

        e_val = round(e_val, 2)
        diff = round(e_val - q_val, 2)
        match_pct = calc_match(e_val, q_val)

        status = "MATCH" if abs(diff) < 1.0 or match_pct >= 99.0 else "DIFF"

        detail_rows.append({
            "category": cat,
            "qbo_item": item_name,
            "erp_account": e_name,
            "qbo_amount": q_val,
            "erp_amount": e_val,
            "difference": diff,
            "match_pct": match_pct,
            "status": status
        })

    return {
        "summary": summary,
        "top_categories": top_categories,
        "all_years": all_years,
        "detail_rows": detail_rows
    }

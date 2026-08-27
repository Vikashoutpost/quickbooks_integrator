# QuickBooks to ERPNext Migration Rulebook & Specification

This document contains the complete set of architectural rules, accounting logic, multi-currency conversion standards, validation bypasses, and audit procedures implemented for the **QuickBooks to ERPNext Integration**.

---

## 1. General Accounting & Chart of Accounts Rules

1. **Company & Base Currency**:
   - Company: `Movam Technologies Limited` (or configured default company).
   - Base Currency: **`NGN` (Nigerian Naira)**.
2. **Official Movam Accounts Only**:
   - Placeholder accounts starting with `QB-` (e.g. `QB-1150040010`) are **strictly prohibited**.
   - All transactions must resolve to official Movam numbered accounts:
     - **Bank Accounts**:
       - `119010 - FCMB Bank - MTL` (NGN)
       - `119020 - Globus Bank - MTL` (NGN)
       - `119030 - Lenco Funding Account - MTL` (NGN)
       - `119040 - Petty Cash - MTL` (NGN - fallback for Cash/Cash in Hand)
       - `119050 - Globus Bank USD - 5000032967 - MTL` (USD)
       - `119060 - Globus Bank USD - 8000006697 - MTL` (USD)
       - `119070 - Movam Inc - MTL` (NGN)
       - `119080 - FCMB USD - MTL` (USD)
       - `119090 - Omnipay/Movam Technologies - MTL` (NGN)
     - **Receivables**:
       - `121010 - Trade Receivables - NGN - MTL` (NGN)
       - `121020 - Trade Receivables - USD - MTL` (USD)
     - **Payables**:
       - `225010 - Trade Creditors - NGN - MTL` (NGN)
       - `225020 - Trade Creditors - USD - MTL` (USD)
     - **Intercompany & Loans**:
       - `228020 - Intercompany - Movam INC - MTL`
       - `224040 - Loan Payable - MTL`
     - **Tax & Rounding**:
       - `230040 - VAT Payable - MTL`
       - `403420 - Round Off - MTL`
3. **3-Tier Account Resolution Pipeline**:
   - **Tier 1 (Explicit Map)**: Exact alias/name matching via dictionary (e.g., `"Other Payable due to related party"` $\rightarrow$ `224040 - Loan Payable - MTL`).
   - **Tier 2 (Database Active Account Match)**: SQL match for active accounts:
     ```sql
     SELECT name FROM `tabAccount` 
     WHERE company = %s AND is_group = 0 AND disabled = 0 AND name NOT LIKE 'QB-%'
     ```
   - **Tier 3 (Category Fallback)**: Fallback by account category (Expense $\rightarrow$ `403440 - Miscellaneous Expenses - MTL`).

---

## 2. Standard Tagging & Dimension Rules

Every transaction is assigned a single standard tag and standard dimensions to ensure 1-click filtering in ERPNext List Views and reports:

| Transaction Type | Tag Assigned | Custom ID Prefix | Dedicated Cost Center |
| :--- | :--- | :--- | :--- |
| **Purchase Bills** | **`QB Bills`** | `{QBO_Id}` | `QuickBooks - MTL` (or mapped) |
| **Sales Invoices** | **`QB Sales`** | `INV-{QBO_Id}` | `QuickBooks - MTL` (or mapped) |
| **Manual Journal Entries** | **`QB Journals`** | `JE-{QBO_Id}` | **`QuickBooks JV - MTL`** |
| **Customer Payments** | **`QB Payments`** | `PAY-{QBO_Id}` | **`QuickBooks Payment - MTL`** |
| **Vendor Bill Payments** | **`QB Payments`** | `BILLPAY-{QBO_Id}` | **`QuickBooks Payment - MTL`** |

- **Tagging Implementation**: The code automatically sets `_user_tags = ",{Tag},"` directly on `tabJournal Entry` and inserts a matching record into `tabTag Link`.

---

## 3. Module-Specific Synchronization Rules

### A. Purchase Bills (`Bill`)
1. **Identifier & Reference**:
   - If `DocNumber` is present: `cheque_no = DocNumber`, `user_remark = f"bills of QBO - {DocNumber}"`.
   - If `DocNumber` is empty: `cheque_no = f"QB-{Id}"`, `user_remark = f"bills of QBO - {Id}"`.
2. **Supplier Assignment**:
   - Auto-create supplier if missing with `supplier_type = "Private Limited Company(Ltd)"` and `flags.ignore_mandatory = True`.
3. **Accounting Entry**:
   - **Debit**: Mapped Expense Head(s) / COGS (`40xxxx`).
   - **Credit**: `225010 - Trade Creditors - NGN - MTL` (or `225020` if USD) with `party_type = "Supplier"`, `party = supplier`.
4. **Attachments**:
   - Query: `SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Value = '{qb_id}'`
   - Download binary and insert into `tabFile` (`attached_to_doctype = "Journal Entry"`).

---

### B. Sales Invoices (`Invoice`)
1. **Identifier & Reference**:
   - `custom_quickbooks_je_id = f"INV-{Id}"`
   - `cheque_no = DocNumber or f"INV-{Id}"`
   - `user_remark = f"Sales invoice of QBO - {DocNumber or Id}"`
2. **Customer Assignment**:
   - Auto-create customer if missing (`flags.ignore_mandatory = True`).
3. **Accounting Entry**:
   - **Debit**: `121010 - Trade Receivables - NGN - MTL` (or `121020` if USD) with `party_type = "Customer"`, `party = customer`.
   - **Credit**: Mapped Sales / Revenue / Service Head(s) (`311010`).

---

### C. Manual Journal Entries (`JournalEntry`)
1. **Reconciliation Target**:
   - **Grand Total**: Must tie 100.0000% to QuickBooks Journal Excel benchmark of **₦790,491,549.11**.
2. **Multi-Currency Balancing Formula**:
   - For multi-currency entries with foreign legs (USD/EUR) in an NGN company:
     $$\text{exchange\_rate} = \frac{\text{target\_base\_amount\_ngn}}{\text{foreign\_amount}}$$
   - Prevents floating-point penny differences without requiring unnatural Round-Off rows.
3. **Historical Residual Balancing (`403420 - Round Off - MTL`)**:
   - For historical entries with internal QBO variances (e.g. 11 historical VAT payment cheques with ₦75 missing bank charges tax row), automatically balance with `403420 - Round Off - MTL` so that the entry submits cleanly while maintaining ₦0.00 net variance across the whole ledger.
4. **Mandatory Party Validation**:
   - When a row uses Receivable (`121010`) or Payable (`225010`), assign `party_type = "Customer"` or `"Supplier"` and link the entity.

---

### D. Customer Payments (`Payment`)
1. **Identifier & Reference**:
   - `custom_quickbooks_je_id = f"PAY-{Id}"`
   - `cheque_no = f"PAY-{DocNumber}" if DocNumber else f"PAY-{Id}"` *(guarantees $\ge 3$ characters to satisfy Frappe reference validation)*.
   - `user_remark = f"Customer Payment QBO - {DocNumber or Id}"`
2. **Accounting Entry**:
   - **Debit**: Resolved Bank Account (`119010`, `119020`, etc.).
   - **Credit**: `121010 - Trade Receivables - NGN - MTL` (or `121020` if USD) with `party_type = "Customer"`, `party = customer`.
3. **Multi-Currency Conversion**:
   - For USD customer payments deposited to NGN Bank:
     - USD Receivable: `$Amount` @ `ExchangeRate`.
     - NGN Bank: `NGN Amount ($Amount * ExchangeRate)` @ `1.0`.

---

### E. Vendor Bill Payments (`BillPayment`)
1. **Identifier & Reference**:
   - `custom_quickbooks_je_id = f"BILLPAY-{Id}"`
   - `cheque_no = f"BP-{DocNumber}" if DocNumber else f"BILLPAY-{Id}"` *(guarantees $\ge 3$ characters)*.
   - `user_remark = f"Bill Payment QBO - {DocNumber or Id}"`
2. **Accounting Entry**:
   - **Debit**: `225010 - Trade Creditors - NGN - MTL` (or `225020` if USD) with `party_type = "Supplier"`, `party = supplier`.
   - **Credit**: Resolved Bank Account (`CheckPayment.BankAccountRef`, `119010`, `119020`, `119050`, etc.).
3. **Zero-Amount Credit Application Rule**:
   - If `TotalAmt == 0` and lines represent JournalEntry/VendorCredit applications with no cash outflow, skip bank journal creation (financial entry already booked in the source Journal Entry).
4. **Multi-Currency Conversion**:
   - For USD vendor payments paid from NGN Bank:
     - USD Payable: `$Amount` @ `ExchangeRate`.
     - NGN Bank: `NGN Amount ($Amount * ExchangeRate)` @ `1.0`.

---

## 4. Production Execution & Safety Rules

1. **ERPNext Bypass Flags**:
   - Always set:
     ```python
     doc.flags.ignore_permissions = True
     doc.flags.ignore_mandatory = True
     doc.flags.ignore_links = True
     ```
   - **CRITICAL**: **DO NOT** use `flags.ignore_validate = True` on `Journal Entry`. Frappe's `validate()` is strictly required to execute `set_amounts_in_company_currency()`, calculate debits/credits, and post `tabGL Entry` records.
2. **Batch Commits & Memory Safety**:
   - Call `frappe.db.commit()` every **50 records** to prevent long-running transaction lockups and memory exhaustion.
3. **Graceful Job Cancellation**:
   - Sync loops check `frappe.cache().get_value("qb_sync_cancel_requested")` every 10 iterations.
   - If cancelled, commits the current batch, publishes a realtime cancellation message, and exits safely without leaving corrupted records.
4. **Auto-Pagination**:
   - All QuickBooks queries use `STARTPOSITION {start} MAXRESULTS 500` in a while loop to pull full datasets (handling 6,000+ records seamlessly).
5. **Real-time User Feedback**:
   - Uses `frappe.publish_progress` and `frappe.publish_realtime` to keep the UI progress bar responsive.

---

## 5. Post-Migration Verification Checklist

When migrating a new production database backup:

```bash
# 1. Restore the new database
bench --site [site-name] restore /path/to/database.sql.gz
bench --site [site-name] migrate

# 2. Open QuickBooks Settings in ERPNext UI
# - Verify OAuth connection is active
# - Click "Fetch Bills" -> Wait for completion (1,057 Bills)
# - Click "Fetch Invoices" -> Wait for completion (325 Invoices)
# - Click "Fetch Journal Entries" -> Wait for completion (809 JEs)
# - Click "Fetch Payments" -> Wait for completion (6,400+ Payments)

# 3. Verification SQL Query (Should return 0 drafts and exact submitted counts)
bench --site [site-name] execute frappe.db.sql --args "['SELECT (SELECT count(*) FROM \`tabJournal Entry\` WHERE custom_quickbooks_je_id LIKE \"PAY-%%\" AND docstatus = 1) as customer_payments, (SELECT count(*) FROM \`tabJournal Entry\` WHERE custom_quickbooks_je_id LIKE \"BILLPAY-%%\" AND docstatus = 1) as bill_payments, (SELECT count(*) FROM \`tabJournal Entry\` WHERE custom_quickbooks_je_id LIKE \"JE-%%\" AND docstatus = 1) as manual_jes, (SELECT count(*) FROM \`tabJournal Entry\` WHERE custom_quickbooks_je_id NOT LIKE \"JE-%%\" AND custom_quickbooks_je_id NOT LIKE \"INV-%%\" AND custom_quickbooks_je_id NOT LIKE \"PAY-%%\" AND custom_quickbooks_je_id NOT LIKE \"BILLPAY-%%\" AND docstatus = 1) as bills, (SELECT count(*) FROM \`tabJournal Entry\` WHERE custom_quickbooks_je_id LIKE \"INV-%%\" AND docstatus = 1) as invoices']"

# 4. Reconciliation Verification for Manual JVs
# Total Debit and Credit for cost_center = 'QuickBooks JV - MTL' must equal ₦790,491,549.11
bench --site [site-name] execute frappe.db.sql --args "['SELECT SUM(debit), SUM(credit) FROM \`tabGL Entry\` WHERE cost_center = \"QuickBooks JV - MTL\" AND is_cancelled = 0']"
```

---

## 6. Solved Edge Cases & Historical Gotchas Registry

This registry documents specific historical accounting problems discovered during integration testing and their permanent solutions:

### A. Zero-Amount Lines & "Incorrect number of General Ledger Entries" Error
- **Problem**: When a QuickBooks payload contained a line with `0.00` amount, inserting it into Frappe created a child row in `tabJournal Entry Account`, but Frappe skipped creating a `tabGL Entry` for zero amounts. Frappe's validator then threw: `"Incorrect number of General Ledger Entries found. You might have selected a wrong Account in the transaction."`
- **Enforced Rule**: Every sync engine strictly filters out rows where both `debit == 0` and `credit == 0` before appending to `doc.accounts`.

### B. Frappe 2-Decimal Precision Pre-Rounding
- **Problem**: Passing floating-point values with $>2$ decimal places (e.g. `144.45389`) caused Frappe to truncate them upon document insertion, creating residual ₦0.01 – ₦0.05 differences.
- **Enforced Rule**: All debit and credit amounts in account currency are explicitly pre-rounded with `round(flt(amount), 2)` before constructing the payload.

### C. Multi-Currency Account Routing for Prepayments
- **Problem**: QuickBooks used the single name "Prepaid SAAS" for both USD software subscriptions and local NGN software. In ERPNext, account heads are currency-bound.
- **Enforced Rule**:
  - If transaction currency is `USD` $\rightarrow$ route to `117090 - Prepaid SAAS - MTL` (USD).
  - If transaction currency is `NGN` $\rightarrow$ route to `116140 - Prepaid SAAS NGN - MTL` (NGN).

### D. Intercompany vs Bank "Movam Inc" Distinction
- **Problem**: QuickBooks contained transactions referencing "Movam Inc" for both bank accounts and intercompany loan movements.
- **Enforced Rule**:
  - Bank/Cash accounts map to `119070 - Movam Inc - MTL` (Bank Account).
  - "Movam Inc. due to/from" and intercompany balances map to `228020 - Intercompany - Movam INC - MTL` (Intercompany Liability).

### E. Staff Operational Advances Routing
- **Problem**: Outdated QuickBooks entries referenced disabled advance accounts.
- **Enforced Rule**: Mapped to active `117010 - Staff Operational Advance - MTL`.

### F. Automatic OAuth Token Refresh Handling
- **Problem**: Intuit OAuth access tokens expire every 60 minutes. Long batch jobs (e.g. 6,000+ payments) will encounter token expiration mid-sync.
- **Enforced Rule**: Whenever an API request returns HTTP `401 Unauthorized`, the sync engine automatically executes `refresh_qb_token()` using `intuitlib.client.AuthClient`, commits new tokens to `Quickbook Settings`, updates the request headers, and retries seamlessly.


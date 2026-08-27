# QuickBooks Synchronization Rules & Architecture Standards

When maintaining, modifying, or testing the QuickBooks integration sync modules in `quickbooks_integration/api/`, always adhere to the following standards:

1. **Official Movam Accounts Only**:
   - Never use placeholder accounts starting with `QB-`.
   - All mapped heads must resolve to official numbered accounts (`119xxx`, `121xxx`, `225xxx`, `228xxx`, `230xxx`, `40xxxx`).

2. **Standardized Tags**:
   - `QB Bills` for Purchase Bills.
   - `QB Sales` for Sales Invoices.
   - `QB Journals` for Manual Journal Entries.
   - `QB Payments` for Customer & Vendor Payments.

3. **Multi-Currency Balancing**:
   - For foreign currency rows (USD), dynamically calculate the effective exchange rate against the base NGN leg so that $\text{Total Debit} = \text{Total Credit}$ down to the exact kobo.

4. **Reference Numbers Length Rule**:
   - Always ensure `cheque_no` has $\ge 3$ characters by prefixing short numbers (`BP-{DocNumber}`, `PAY-{DocNumber}`).

5. **Production Safeguards**:
   - Use `flags.ignore_permissions = True`, `flags.ignore_mandatory = True`, and `flags.ignore_links = True`.
   - Never use `flags.ignore_validate = True` on `Journal Entry` as Frappe needs `validate()` to calculate company currency amounts and post `tabGL Entry`.

6. **Grand Total Benchmark for Manual JVs**:
   - Benchmark total for `cost_center = 'QuickBooks JV - MTL'` is **₦790,491,549.11** exact match.

7. **Zero-Amount Lines Filter**:
   - Never append account rows where both `debit == 0` and `credit == 0` (avoids Frappe's `"Incorrect number of General Ledger Entries found"` error).

8. **2-Decimal Pre-Rounding**:
   - Explicitly apply `round(flt(amount), 2)` before creating `Journal Entry` payloads to prevent float truncation residuals.

9. **Currency-Bound Prepayment Routing**:
   - "Prepaid SAAS" in USD $\rightarrow$ `117090 - Prepaid SAAS - MTL`.
   - "Prepaid SAAS" in NGN $\rightarrow$ `116140 - Prepaid SAAS NGN - MTL`.

10. **Intercompany vs Bank Distinction**:
    - "Movam Inc" Bank $\rightarrow$ `119070 - Movam Inc - MTL`.
    - "Movam Inc. due to/from" $\rightarrow$ `228020 - Intercompany - Movam INC - MTL`.

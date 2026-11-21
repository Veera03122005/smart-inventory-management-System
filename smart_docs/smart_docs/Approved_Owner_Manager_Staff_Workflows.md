# SmartStock AI — Approved Owner, Manager and Staff Workflows

**Document purpose:** Authoritative workflow and permission reference for the SmartStock AI V1 audit.

**Scope:** This document consolidates the previously approved role boundaries, operational workflows, inventory-accounting rules and exception handling. It does not claim that the current code implements every requirement; implementation must be verified separately.

## 1. Product boundary

SmartStock AI V1 is an IoT-enabled restaurant inventory management and intelligence platform. It is not a complete restaurant ERP.

V1 includes:
- Owner, Manager and Staff role-based workflows.
- Shared inventory ledger and balance projection.
- Opening stock, supplier deliveries, closing stock and document-assisted entry.
- Supplier, invoice and batch tracking.
- IoT monitoring and barcode-based refill workflow.
- Low-stock, expiry and operational alerts.
- Demand forecasting and operational reporting.
- Manager depletion investigation and wastage classification.

V1 does not include POS/order management, recipe/BOM-based automatic consumption, payroll, staff scheduling, table reservations, customer management, multi-branch management, or automatic purchase-order placement.

## 2. Roles and permissions

### 2.1 Owner

The Owner has full governance, operational and financial visibility:
- View dashboard, inventory and operational status.
- View sales/revenue, purchase costs, unit costs, stock valuation and profit/food-cost metrics only where supported by reliable underlying data.
- Create and manage Managers and Staff.
- Manage suppliers, inventory configuration, IoT devices, alerts and reports.
- Review audit history and system-level operational information.

### 2.2 Manager

The Manager has operational management and sales visibility:
- View sales figures and sales reports.
- Monitor inventory, opening/closing submissions and supplier deliveries.
- Investigate depletion and classify eligible losses.
- Monitor IoT devices, refill activity and variance.
- Create, deactivate, reactivate and manage Staff accounts within the permitted Staff scope.
- View operational reports and alerts.

The Manager must not receive:
- Purchase costs or ingredient unit costs.
- Stock valuation.
- Gross/net profit, margins or cost-derived financial analytics.
- Food-cost valuation or monetary wastage valuation.

The Manager cannot create/promote an Owner, modify Owner/Manager accounts, or change their own role.

### 2.3 Staff

Staff perform daily inventory operations:
- Record physical opening stock.
- Record supplier deliveries and invoice details.
- Upload supported stock/invoice documents.
- Review and correct their own staged extracted data.
- Explicitly verify valid data before posting.
- Record physical closing stock.
- Scan barcodes and perform permitted IoT refill steps.
- View operational stock, alerts and their own submission history.

Staff must not access:
- Sales/revenue or purchase-cost analytics.
- Stock valuation, profit or margins.
- Manager/Owner endpoints or user administration.
- Wastage classification and depletion investigation.
- Posted-ledger editing.
- Another Staff member's staged documents.

**Security rule:** Backend authorization is mandatory. Hiding a frontend control is not authorization.

## 3. Traditional Staff workflow

### 3.1 Opening stock
1. Staff physically counts ingredient stock at the start of the business day.
2. Staff submits opening quantities with ingredient and unit details.
3. The system compares the physical opening count with the prior book balance.
4. Any discrepancy is posted as an auditable opening adjustment.
5. Corrections to an already-posted opening count must reverse/replace the prior adjustment safely and idempotently.

### 3.2 Supplier delivery
1. Staff records supplier and invoice details.
2. Staff records invoice lines, quantities, units, prices and batch/expiry information where applicable.
3. Documents may be uploaded for extraction into a staged record.
4. Staff reviews and corrects staged data.
5. Staff explicitly verifies the submission.
6. A valid supplier receipt posts one `STOCK_IN` movement to consolidated restaurant inventory.
7. Duplicate invoices/submissions must not post twice.
8. Multiple batches of the same ingredient on one invoice must be supported.
9. Units must be normalized safely (for example kg/g and L/ml); unknown or incompatible units must be rejected rather than guessed.

### 3.3 Document staging and verification
1. Uploading a document creates staged data only; it must not directly change inventory.
2. Extracted fields remain reviewable and correctable by the uploading Staff member.
3. Staged edits must persist on the backend.
4. Staff must explicitly verify before posting.
5. Only the uploader may view, edit, download and post their staged document.
6. Posting must be atomic and idempotent.
7. CSV, XLSX and PDF parsing are in scope. Image OCR is not implemented in the documented baseline and must not be represented as available unless separately implemented and tested.
8. Original files must be retained safely and downloads must be authenticated and path-traversal protected.

### 3.4 Closing stock
1. Staff physically counts closing stock.
2. The system calculates depletion from opening stock plus receipts minus physical closing stock, subject to the approved accounting rules.
3. Closing reconciliation posts the stock reduction exactly once.
4. Eligible unexplained depletion is recorded for Manager investigation.
5. Staff does not enter or classify wastage.

## 4. IoT-enabled Staff refill workflow

1. Staff scans the ingredient/container barcode.
2. Staff enters billed ingredient weight and billed price.
3. The system captures a stable pre-refill sensor weight.
4. Staff physically refills the monitored container.
5. The system captures a stable post-refill sensor weight.
6. Measured refill quantity is calculated as post-refill weight minus pre-refill weight.
7. The system compares billed quantity with measured refill quantity and records the variance.
8. Supplier receipt and container refill are separate accounting events.
9. Supplier receipt increases consolidated restaurant stock once.
10. Internal transfer into a monitored container has zero consolidated stock effect.
11. Refill completion must be atomic, auditable and idempotent.
12. Stale, unstable or disconnected sensor readings must not be substituted with fabricated or stale values to complete a refill.

## 5. Shared inventory accounting rules

### 5.1 Authoritative ledger
- `inventory_transactions` is the authoritative append-only inventory ledger.
- `inventory_balances` is a projection/cache and must reconcile to the ledger.
- Posted transactions are immutable.
- Corrections use auditable reversal/correction events, not silent edits.
- Multi-row posting must be transactional and idempotent.

### 5.2 Supplier receipt versus container refill
- Supplier receipt: `STOCK_IN`, increases consolidated restaurant stock once.
- Container refill: internal transfer, zero consolidated stock effect (`delta_qty = 0`).
- Do not count a supplier delivery and its subsequent container refill as two increases in restaurant stock.

### 5.3 Opening and closing counts
- Opening/closing counts are physical observations.
- Opening discrepancy must be represented by an auditable adjustment.
- Closing reconciliation records depletion once.
- Do not infer expected consumption from recipes unless validated recipe/BOM and POS sales-to-ingredient mapping exist.

### 5.4 Wastage classification — critical zero-sum rule
Closing reconciliation already reduces book stock to match physical closing stock. If a Manager later classifies part of that depletion as spoilage, damage or another category, the classification must not deduct stock again.

- Classification is a zero-sum reclassification event (`delta_qty = 0`).
- Reversal is also zero-sum.
- Classification metadata must reference the eligible original depletion/closing record.
- Classified quantity must never exceed eligible depletion.
- Partial classification is allowed; remaining depletion stays unclassified.
- Classification must be concurrency-safe and idempotent.
- Wastage classified after closing must not create another negative inventory movement.
- If a loss is recorded before closing, it may be posted once, and closing reconciliation must account for it. Do not mix the two accounting paths.

### 5.5 Categories
Approved categories:
- `SPOILAGE`
- `EXPIRED`
- `PREPARATION_LOSS`
- `SPILLAGE`
- `DAMAGE`
- `THEFT`
- `MEASUREMENT_ERROR`
- `NORMAL_CONSUMPTION`
- `OTHER_UNEXPLAINED`

Explanatory notes are mandatory for `THEFT` and `OTHER_UNEXPLAINED`.

## 6. Manager depletion investigation workflow

1. Manager reviews eligible depletion records.
2. Manager investigates the operational reason for depletion.
3. Manager may add timestamped notes.
4. Manager may split depletion across approved categories.
5. The system enforces the remaining eligible quantity limit.
6. Partial or unresolved quantity remains unclassified.
7. Manager may resolve the investigation when appropriate.
8. Reversals must be auditable compensating events and restore classification availability without changing inventory balance.
9. Manager sees quantities and operational information, not purchase costs or rupee valuation.
10. Staff is denied access at the backend.

## 7. Audit acceptance principles

A workflow is not considered verified merely because a UI screen exists or a test name appears in a report. Verification must include:
- Backend endpoint and authorization inspection.
- Database constraints and transaction behavior.
- Positive and negative role tests.
- Duplicate/retry behavior.
- Partial and reversal behavior.
- Concurrency tests where quantities are bounded.
- Ledger-to-balance reconciliation.
- Tests on disposable database copies for migration-sensitive scenarios.
- Clear distinction between simulated IoT tests and physical ESP32/HX711 tests.

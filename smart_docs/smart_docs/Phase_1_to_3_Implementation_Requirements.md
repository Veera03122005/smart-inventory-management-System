# SmartStock AI — Phase 1, Phase 2, Phase 2.1 and Phase 3 Requirements

**Document purpose:** Phase-by-phase acceptance criteria for auditing the implementation against the approved V1 workflow.

**Important:** This is a requirements and acceptance document, not proof that the phases are implemented. Completion claims must be supported by source inspection and tests executed during the audit.

## Phase 1 — RBAC and financial redaction

### Required implementation
1. Enforce Owner, Manager and Staff authorization in backend routes and service functions.
2. Enforce active-account status on every authenticated request.
3. Owner has full authorized operational and financial access.
4. Manager can access sales information but not purchase costs, unit costs, stock valuation, profit, margins or monetary wastage valuation.
5. Staff cannot access sales/revenue, financial analytics, Manager/Owner endpoints, user administration or wastage investigation.
6. Manager may administer Staff accounts only.
7. Manager cannot create/promote Owner, modify Owner/Manager accounts, or change own role.
8. Sensitive fields must be redacted in every API response, export and alternate endpoint.
9. Role changes must not leave stale JWT/session claims with revoked privileges.

### Acceptance tests
- Direct API tests for every role.
- Staff receives 403 for restricted routes.
- Manager responses omit or null protected financial values.
- Owner receives permitted financial values.
- Inactive accounts are rejected.
- Existing sessions are checked after role changes.
- Frontend route guards are tested, but are not accepted as a substitute for backend authorization.

## Phase 2 — Traditional Staff workflows

### Required implementation
1. Physical opening stock entry.
2. Supplier delivery and invoice entry.
3. Document upload and extraction staging.
4. Staff review and correction of staged data.
5. Explicit Staff verification before posting.
6. Physical closing stock entry and reconciliation.
7. Supplier and invoice line tracking.
8. Duplicate invoice protection.
9. Batch/expiry support.
10. Historical records remain intact.

### Acceptance tests
- Upload does not directly change inventory.
- Staff can persist edits to their own staged records.
- Staff cannot access another Staff member's staged records.
- Posting requires explicit verification.
- Repeated posting does not duplicate ledger movements.
- Closing reconciliation records depletion once.
- Original uploaded file can be retrieved through an authenticated route.
- CSV/XLSX/PDF handling is tested.
- Image OCR is not claimed unless implemented and tested.

## Phase 2.1 — Critical accounting, ownership and unit corrections

### Required implementation
1. Opening discrepancy posts an auditable `ADJUSTMENT`.
2. Corrected opening counts safely reverse/replace the prior discrepancy adjustment.
3. Staff and Manager delivery responses redact `unit_price_rs` and `line_total_rs`; Owner may see them.
4. Staged-document GET, PUT, file download and posting enforce uploader ownership.
5. Multiple batches of the same ingredient on one invoice are supported.
6. Unit normalization supports kg/g and L/ml.
7. Unknown or incompatible units are rejected.
8. Original billed unit and quantity remain retained for audit.
9. Item-level idempotency prevents duplicate posting.

### Required accounting scenario
Previous closing: 20 kg  
Physical opening: 18 kg  
Opening discrepancy: -2 kg  
Supplier delivery: +10 kg  
Closing depletion: -6 kg  
Expected final balance: 22 kg.

### Acceptance tests
- Verify the above scenario against both ledger and balance projection.
- Correct an opening count and verify the previous adjustment is compensated.
- Submit duplicate invoice and delivery requests.
- Include multiple batches of the same ingredient in one invoice.
- Test kg/g and L/ml conversion.
- Test incompatible and unknown units.
- Attempt cross-Staff access to staged data and files.
- Verify financial redaction through direct API responses and exports.

## Phase 3 — Manager depletion investigation and zero-sum wastage classification

### Required accounting rule
Closing reconciliation already records depletion. Manager classification after closing must therefore be a zero-sum reclassification (`delta_qty = 0`) and must not deduct inventory again.

### Required implementation
1. Create eligible depletion records from closing reconciliation.
2. Provide Manager/Owner investigation views.
3. Support the nine approved categories:
   - `SPOILAGE`
   - `EXPIRED`
   - `PREPARATION_LOSS`
   - `SPILLAGE`
   - `DAMAGE`
   - `THEFT`
   - `MEASUREMENT_ERROR`
   - `NORMAL_CONSUMPTION`
   - `OTHER_UNEXPLAINED`
4. Require explanatory notes for `THEFT` and `OTHER_UNEXPLAINED`.
5. Support partial classification.
6. Enforce classified quantity <= eligible remaining depletion.
7. Keep unclassified quantity visible.
8. Record actor, timestamp, notes, category and reference to the eligible depletion.
9. Support investigation notes and resolution status.
10. Support auditable classification reversal.
11. Classification and reversal both have `delta_qty = 0`.
12. Reversal restores available classification quantity.
13. Prevent duplicate and concurrent over-classification.
14. Staff receives no access to investigation endpoints.
15. Manager responses contain no purchase costs, unit costs, rupee valuation or profit.
16. Owner may access permitted financial investigation/report fields.

### Required acceptance tests
- Full classification.
- Partial classification.
- Over-classification rejected.
- Reverse classification and reclassify.
- Duplicate request behavior.
- Concurrent classification requests.
- Invalid/ineligible depletion reference rejected.
- Notes requirements enforced.
- Staff direct API denial.
- Manager financial redaction.
- Owner financial visibility.
- Inventory balance unchanged after classification and reversal.
- Ledger transaction records remain auditable and immutable.

## Cross-phase invariants

These rules apply to all phases:
- One authoritative append-only `inventory_transactions` ledger.
- `inventory_balances` must reconcile with ledger movements.
- Supplier receipt increases consolidated stock once.
- Internal container refill has zero consolidated stock effect.
- Posted ledger records are not silently edited.
- Corrections use compensating events.
- Multi-step posting is atomic and idempotent.
- No double deduction of consumption or wastage.
- No recipe-based expected consumption without validated BOM and POS mapping.
- Backend authorization and financial redaction are mandatory.
- Historical data must remain intact across migrations.

## Phase 4 boundary — not part of Phases 1–3

Phase 4 is the enhanced IoT refill workflow and must be audited/implemented separately:
1. Barcode identifies ingredient/container.
2. Staff enters billed weight and billed price.
3. Capture stable pre-refill sensor weight.
4. Physically refill container.
5. Capture stable post-refill sensor weight.
6. Calculate measured refill quantity.
7. Compare billed and measured quantity.
8. Record variance for investigation.
9. Keep supplier receipt and internal container transfer as separate accounting events.
10. Reject stale, unstable or disconnected sensor readings.
11. Make completion atomic, idempotent and auditable.
12. Test simulated sensor behavior separately from real ESP32/HX711 hardware.

## Audit reporting rule

For every acceptance criterion, report:
- Actual implementation file/function/endpoint.
- Relevant schema/table/constraint.
- Relevant test and exact assertion.
- Whether the test was actually executed.
- Status: PASS / FAIL / PARTIAL / NOT IMPLEMENTED / NOT VERIFIED.
- Severity and evidence.

Do not infer completion from a prior Antigravity report alone.

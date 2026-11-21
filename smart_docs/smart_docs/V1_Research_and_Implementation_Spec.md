# SmartStock AI --- V1 Research and Implementation Specification

> **Immediate build specification for a focused, measurable research
> prototype.**
>
> V1 is not the complete commercial SaaS platform. Its purpose is to
> establish a reliable inventory data foundation and produce defensible
> experimental results for provenance-aware demand forecasting and
> inventory discrepancy analysis.

**Version:** 1.0\
**Date:** 18 November 2026\
**Relationship to product vision:** This document defines what should be
built now. The long-term product scope is documented in
`README_SmartStock_AI.md`.

------------------------------------------------------------------------

## 1. Executive summary

SmartStock AI V1 is a restaurant inventory research prototype combining:

-   A ledger-based inventory workflow.
-   Manual and Excel/CSV data capture with review-before-post.
-   One real ESP32 + HX711 + load-cell measurement setup for one
    selected ingredient.
-   Recipe-based theoretical consumption derived from sales data.
-   Actual consumption recorded in the inventory ledger.
-   Forecasting baselines and a machine-learning model.
-   Provenance-aware analysis that distinguishes measured, manually
    entered, imported, and predicted data.

The V1 must demonstrate a working end-to-end pipeline and report
measured results. A visually complete dashboard without validated data
flow and reproducible evaluation is not a successful V1.

## 2. Research problem

Restaurant inventory data can originate from different channels and have
different reliability characteristics. Manual records may be delayed or
inconsistent; document imports may contain extraction errors; IoT
readings may be noisy or incomplete. Conventional forecasting pipelines
often treat all historical values as equally reliable.

The research explores whether retaining data provenance and
incorporating hybrid observations can improve forecasting and help
identify operational discrepancies.

### Research question

**Can provenance-aware hybrid inventory data improve restaurant
ingredient demand forecasting and operational discrepancy detection
compared with conventional historical inventory data?**

### Objectives

1.  Implement a traceable inventory ledger.
2.  Preserve the origin and capture method of each relevant
    observation/transaction.
3.  Build a repeatable data import and verification workflow.
4.  Collect real readings from one physical load-cell setup.
5.  Calculate theoretical ingredient consumption from recipe quantities
    and sales.
6.  Compare theoretical consumption with actual ledger-recorded
    consumption.
7.  Evaluate simple forecasting baselines against a selected ML model.
8.  Quantify whether IoT observations add useful temporal detail or
    discrepancy signals.
9.  Document limitations and avoid unsupported generalization.

## 3. V1 scope

### Build now

  -----------------------------------------------------------------------
  Area                                V1 implementation
  ----------------------------------- -----------------------------------
  Deployment context                  One restaurant

  Users                               Owner/admin and staff

  Authentication                      Basic secure login and server-side
                                      authorization

  Inventory ledger                    Stock-in, internal transfer,
                                      consumption, wastage, stock count
                                      and adjustment

  Ingredient master                   Ingredient, base unit, category and
                                      storage location

  Data import                         Excel and CSV

  Import safety                       Preview, validation, staff
                                      correction/confirmation, then
                                      posting

  IoT                                 One ESP32 + HX711 + load cell, one
                                      selected ingredient

  Sales input                         CSV import for analytics; no full
                                      POS

  Recipe/BOM                          Ingredient quantity per menu
                                      item/portion

  Analytics                           Stock history, usage, wastage,
                                      variance, data provenance

  Forecasting                         Seasonal-naive and moving-average
                                      baselines plus one ML model

  Evaluation                          Time-based validation with MAE,
                                      RMSE and WAPE where appropriate

  Reporting                           Reproducible experiment results and
                                      limitations
  -----------------------------------------------------------------------

### Explicitly defer

-   Multi-tenant SaaS and owner-managed multiple restaurants.
-   Full RLS and complex tenant administration.
-   Complete POS billing/payment workflows.
-   Automatic POS-to-inventory deduction.
-   Barcode workflows unless already stable and required for the demo.
-   Native Android application.
-   Offline PWA transaction synchronization.
-   Arbitrary handwritten, mixed-language OCR.
-   Complex supplier/procurement features.
-   Microservices, distributed outbox architecture, and infrastructure
    not needed for the prototype.
-   Large-scale role hierarchy and advanced separation-of-duties
    workflows.

Do not build deferred features merely because they appear in the
long-term README.

## 4. V1 users and permissions

### Owner/admin

-   Manage the single prototype restaurant.
-   Create/edit ingredient and storage master data.
-   Import sales CSV and review analytics.
-   View inventory, forecast, and discrepancy reports.
-   Manage staff access.

### Staff

-   Record permitted stock movements.
-   Upload Excel/CSV inventory records.
-   Review imported rows and correct errors.
-   Record counts, consumption, and wastage.
-   View permitted operational information.

Even in a single-restaurant prototype, the backend must verify
authentication and role permissions. Do not rely on frontend route
hiding.

## 5. Core inventory model

### 5.1 Ledger events

Use a canonical transaction table or equivalent domain model. Minimum
transaction types:

-   `STOCK_IN`
-   `TRANSFER_OUT`
-   `TRANSFER_IN`
-   `CONSUMPTION`
-   `WASTAGE`
-   `ADJUSTMENT_IN`
-   `ADJUSTMENT_OUT`

Internal transfers must update source and destination locations
atomically and must not change the restaurant's consolidated stock.

### 5.2 Balance equation

``` text
Closing =
  Opening
  + Stock In
  + Transfers In
  - Transfers Out
  - Consumption
  - Wastage
  + Adjustments
```

For consolidated restaurant stock, internal transfer legs cancel out.

### 5.3 Ledger rules

-   Posted events are not overwritten.
-   Corrections are represented by reversal/correction events.
-   Balances are derived projections and must reconcile to ledger
    events.
-   Use database transactions for multi-row operations.
-   Use idempotency keys or equivalent duplicate protection for
    retryable writes.
-   Use decimal-safe quantities or integer-scaled base units.
-   Keep consumption separate from wastage.
-   A closing balance in a register is a snapshot, not a stock-in event.
-   Missing cost must remain missing; do not fabricate valuation.

### 5.4 Provenance fields

For relevant observations and transactions, record:

-   `source_type`: `MANUAL`, `EXCEL_IMPORT`, `CSV_IMPORT`, `IOT`,
    `DOCUMENT`
-   `measurement_method`: `MANUAL`, `IOT`, `HYBRID`, where applicable
-   `capture_channel`: `MANUAL_FORM`, `EXCEL_IMPORT`, `CSV_IMPORT`,
    `IOT_INGESTION`
-   `source_record_id` or source file reference.
-   `recorded_by`.
-   `observed_at` and `recorded_at`.
-   `verification_status`.
-   `confidence` only when it has a defined meaning (for example, OCR
    extraction confidence); do not invent a generic confidence score for
    manually entered facts.

Do not conflate the physical measurement method with the channel through
which a value was entered.

## 6. Authoritative source policy

A rigid rule that completely rejects all manual input for an
IoT-monitored ingredient is unsafe. Sensors fail, require calibration,
and may be unavailable.

For V1, configure the primary consumption source for the selected
ingredient and distinguish:

1.  **Authoritative posted event:** the source allowed to create normal
    consumption transactions.
2.  **Observation/reconciliation input:** alternate-channel data
    retained for comparison but not automatically posted as consumption.
3.  **Exception workflow:** an authorized user can resolve sensor
    failure or physical-count discrepancies with an auditable
    correction.

Example: if the monitored kitchen container is configured as
IoT-primary, a manual usage entry should be stored as an observation or
flagged for review rather than creating a second consumption transaction
automatically. A verified physical count or sensor-failure adjustment
remains possible through an explicit workflow.

This reduces duplicates by design without making the system unusable
during hardware failure.

## 7. Excel/CSV import workflow

### Supported V1 inputs

-   `.xlsx`
-   `.csv`

PDF extraction and handwritten OCR are deferred unless a small,
controlled template can be reliably demonstrated.

### Workflow

1.  Staff uploads a file.
2.  Backend validates file type, size, and structure.
3.  Parser extracts rows and preserves source sheet/row/column
    references.
4.  User maps columns to known fields.
5.  System matches ingredient names to the ingredient master and flags
    ambiguous matches.
6.  Validation checks dates, units, numeric values, required fields,
    duplicate candidates, and transaction semantics.
7.  Staff previews and corrects the data.
8.  User explicitly chooses analysis-only or inventory import.
9.  Analysis-only creates a report and no ledger events.
10. Inventory import posts only eligible, reviewed rows in a database
    transaction.
11. Import summary reports accepted, rejected, duplicate, and
    review-required rows.

Never interpret a closing-balance column as stock-in. Never post an
unreviewed spreadsheet automatically.

## 8. IoT proof of concept

### Hardware

-   ESP32.
-   HX711 amplifier.
-   One load cell of an appropriate capacity.
-   One fixed ingredient/container installation.
-   Wi-Fi connection to the backend.

### V1 IoT objectives

-   Capture timestamped raw readings.
-   Store device identity and sequence number.
-   Record calibration factor and calibration date.
-   Display raw and filtered/stable readings.
-   Show last-seen status.
-   Detect stale, duplicate, and implausible readings.
-   Compare measured weight changes with manually recorded events.
-   Demonstrate one controlled refill or consumption-observation
    scenario.

### Important limitations

Load cells can drift due to temperature, mounting, vibration, container
handling, moisture, and calibration changes. A sensor reading is not
automatically a stock transaction. Treat the device as a high-frequency
reference signal for a selected high-value/high-volume ingredient, not
as proof that all restaurant inventory can be measured this way.

Document calibration procedure, tare weight, sampling/filtering method,
stable-reading threshold, and observed error. Do not claim
production-grade accuracy based only on a successful demo.

## 9. Recipe/BOM and theoretical consumption

This is a key V1 analytics capability.

### Minimum data

-   Menu item identifier/name.
-   Ingredient identifier.
-   Standard ingredient quantity per portion.
-   Unit.
-   Effective recipe version/date where changes are supported.
-   Sales quantity by menu item and time period.

### Calculation

For ingredient (i) and period (t):

``` text
TheoreticalUsage(i, t) =
  SUM over menu items m [
    SalesQuantity(m, t) * RecipeQuantity(m, i)
  ]
```

Example:

-   Sales: 20 portions of chicken biryani.
-   Standard chicken per portion: 150 g.
-   Theoretical chicken usage: 20 × 150 g = 3,000 g = 3 kg.
-   Actual ledger-recorded consumption: 3.8 kg.
-   Variance: actual − theoretical = 0.8 kg.

``` text
UsageVariance = ActualUsage - TheoreticalUsage

VariancePercentage =
  (ActualUsage - TheoreticalUsage) / TheoreticalUsage * 100
```

Guard against zero theoretical usage. State the sign convention clearly.

### Interpretation

A positive variance is a signal for investigation, not proof of theft.
Possible causes include over-portioning, unrecorded wastage, recipe
inaccuracy, sales timing mismatch, measurement error, or pilferage. The
application should explain and surface discrepancies, not accuse staff.

Recipe versions, serving-size changes, complimentary meals,
cancellations, refunds, staff meals, and menu substitutions can affect
the comparison. Record or explicitly exclude these factors in the
experiment.

## 10. Sales data without a full POS

Import sales data from a CSV for V1. This provides a read-only analytics
input.

Minimum fields:

-   Business date/time.
-   Menu item ID or normalized item name.
-   Quantity sold.
-   Order status or inclusion flag if available.
-   Optional cancellation/refund indicator.

Sales data can feed: - Theoretical recipe consumption. - Daily
ingredient demand targets. - Forecast features. - Sales-versus-usage
discrepancy analysis.

**Sales imports must not create inventory consumption transactions.**
POS/inventory operational coupling remains excluded.

## 11. Forecasting experiment

### 11.1 Forecast target

Define the target as:

**Daily actual ingredient consumption (base unit) for each selected
ingredient.**

If the actual dataset only supports daily stock usage rather than true
consumption, state that limitation and use the correct target name. Do
not relabel stock movement as demand without justification.

Forecast horizon for the initial experiment: next-day demand. Longer
horizons can be explored only if the data supports them.

### 11.2 Candidate methods

Use at least these baselines:

1.  **Seasonal-naive:** predict the value from the corresponding
    previous seasonal period (for daily data, previous week where a full
    weekly pattern is justified).
2.  **Moving average:** predict using a fixed trailing window, with the
    window selected on training/validation data only.

Compare with one ML model:

3.  **Gradient-boosted trees** (for example, XGBoost or
    HistGradientBoosting) using lag features and calendar features.

Prophet may be tested as an additional model if the dataset is large and
sufficiently regular, but it is not mandatory. Do not add multiple
models without enough data to evaluate them properly.

### 11.3 Features

Potential features, subject to data availability: - Lagged daily
consumption (1, 2, 7, 14 days). - Rolling mean/median over prior
windows. - Day of week. - Weekend/holiday indicator if reliable calendar
labels exist. - Sales quantity for relevant menu items, where available
before the forecast cutoff. - Recipe-derived theoretical usage. - Data
provenance indicators or source-quality flags. - IoT-derived summary
features, such as stable weight-change totals or missing-reading
indicators.

Avoid data leakage. Every feature must have been available at the time
the forecast would have been made. Do not use future actual values in
rolling features or validation predictions.

### 11.4 Validation design

-   Use chronological train/validation/test splits.
-   Prefer rolling-origin evaluation when enough history exists.
-   Fit preprocessing and model selection using training/validation
    only.
-   Keep the final test period untouched until model selection is
    complete.
-   Compare all models on the same dates and target values.
-   Report the number of observations and missing days.
-   Clearly mark synthetic/simulated data; do not mix it into real-data
    claims.

Three to four weeks of data can demonstrate an end-to-end prototype and
preliminary evaluation, but it is not enough to make strong claims about
seasonality or generalization. Collect more history where possible and
state the limitation.

### 11.5 Metrics

Report: - MAE. - RMSE. - WAPE where meaningful.

MAPE is unstable or undefined when actual values are zero or near zero,
so do not use it as the only metric for intermittent ingredients.

Define WAPE explicitly:

``` text
WAPE = SUM(ABS(actual - forecast)) / SUM(ABS(actual)) * 100
```

If the denominator is zero, report the metric as undefined for that
evaluation window.

Report metrics per ingredient and overall only with a clear aggregation
method. Include a naive baseline; an ML model is not useful merely
because it is more complex.

## 12. Provenance-aware experiment

The system should preserve provenance as data, then evaluate whether it
provides useful information.

Suggested comparisons:

-   **Experiment A:** manual/import historical data only.
-   **Experiment B:** same data plus available IoT-derived features.
-   **Experiment C:** provenance-aware model/features or quality flags,
    compared against a model that ignores provenance.

Do not claim provenance improves accuracy until the experiment
demonstrates it. A source flag may help identify lower-quality
observations, but it can also encode operational patterns or
missingness. Analyze this carefully.

For discrepancy detection, compare: - Recipe-derived theoretical
usage. - Ledger-recorded actual usage. - IoT-derived measured change
where interpretable. - Manual observations and verified counts.

Report precision/recall only if a defensible labelled anomaly ground
truth exists. Otherwise report case studies and flagged discrepancy
counts, clearly labelled exploratory.

## 13. Data collection plan

Prioritize real restaurant records with permission.

Collect: - Daily opening/closing balances. - Stock-in quantities. -
Consumption/usage entries. - Wastage. - Stock counts and adjustments. -
Menu-item sales quantities. - Recipe ingredient quantities. - IoT
readings and calibration events.

For each record retain source and capture timestamps. An event recorded
today for yesterday's activity must preserve both `observed_at` and
`recorded_at`.

If real data cannot be obtained: - Use synthetic data only for
development/testing. - Label synthetic data in UI, charts, reports, and
research writing. - Do not present synthetic results as field
validation. - Explain data limitations explicitly.

### Printed register recommendation

If paper capture is required, use a controlled printed template: - Fixed
ingredient identifiers/names. - Fixed units. - Boxed numeric cells. -
One date per sheet or clearly defined date range. - Separate opening,
stock-in, usage, wastage, and closing columns. - No ambiguous free-form
unit abbreviations.

Start with typed Excel/CSV before attempting arbitrary handwritten,
mixed-language OCR.

## 14. V1 architecture

Use a simple modular architecture. Avoid infrastructure that does not
contribute to the experiment.

``` text
React + TypeScript UI
        |
        v
     Flask API
        |
        +-- Authentication / role checks
        +-- Ingredient and location master
        +-- Inventory ledger and validation
        +-- Excel/CSV import and review
        +-- IoT telemetry ingestion
        +-- Recipe and sales analytics
        +-- Forecasting/evaluation service
        |
        v
     Relational database

ESP32 + HX711 ---> authenticated telemetry endpoint

Excel/CSV ---> import preview ---> validation ---> review ---> ledger (if approved)
Sales CSV ---> analytics input only ---> theoretical usage / forecasting
```

For a single-site research prototype, SQLite may be acceptable for local
demonstration if transaction behavior and concurrency limitations are
understood. PostgreSQL is preferable when the existing app already uses
it or when deployment/concurrency needs require it. Do not perform a
database migration solely to appear production-oriented; make it based
on actual requirements.

Keep the code modular, but a modular monolith is sufficient. Do not
introduce microservices, Redis, distributed outbox, or complex offline
synchronization for V1 unless a specific tested need requires them.

## 15. Suggested V1 data entities

A minimal schema may include:

-   `users`
-   `ingredients`
-   `units` and `unit_conversions`
-   `storage_locations`
-   `ingredient_location_configs`
-   `inventory_transactions`
-   `inventory_balances` (derived projection, optional)
-   `inventory_batches` (if batch/expiry is in the experiment)
-   `stock_counts`
-   `import_jobs`
-   `import_rows`
-   `iot_devices`
-   `iot_readings`
-   `iot_calibrations`
-   `menu_items`
-   `recipes`
-   `recipe_ingredients`
-   `sales_imports`
-   `sales_lines`
-   `forecast_runs`
-   `forecast_predictions`
-   `audit_logs`

Use foreign keys and constraints. Add `restaurant_id` only if the
prototype needs it now; keep the long-term migration path in mind
without building full multi-tenant administration in V1.

## 16. V1 UI screens

### Owner/admin

-   Overview dashboard.
-   Ingredient/category management.
-   Storage location management.
-   Staff management.
-   Inventory ledger and stock balances.
-   Excel/CSV import.
-   Sales CSV import.
-   Recipe/BOM editor.
-   Forecast and evaluation dashboard.
-   Theoretical-versus-actual usage report.
-   IoT device/reading view.

### Staff

-   Task-focused dashboard.
-   Stock-in.
-   Transfer/refill.
-   Consumption and wastage entry.
-   Stock count.
-   Excel/CSV upload and review.
-   Import history.
-   IoT reading/status view where applicable.

Do not spend the V1 deadline implementing every screen at commercial
SaaS polish. Prioritize working data paths and clear evidence.

## 17. V1 API outline

Illustrative endpoint families:

``` text
/api/auth/*
/api/me
/api/ingredients
/api/storage-locations
/api/inventory/balances
/api/inventory/transactions
/api/inventory/stock-in
/api/inventory/transfers
/api/inventory/counts
/api/inventory/consumption
/api/inventory/wastage
/api/imports
/api/imports/{id}/preview
/api/imports/{id}/validate
/api/imports/{id}/approve
/api/iot/telemetry
/api/iot/readings
/api/sales/imports
/api/recipes
/api/analytics/theoretical-actual
/api/forecasts
/api/forecasts/evaluation
```

All writes require backend validation and authorization. Use idempotency
for retryable transaction creation.

## 18. Security and quality minimum

Even a prototype must: - Hash passwords securely. - Keep secrets out of
source control. - Enforce backend role checks. - Validate all request
data. - Restrict CORS to required origins. - Avoid tokens in query
strings. - Validate upload size and file content. - Store uploaded files
safely. - Avoid exposing stack traces or secrets. - Use database
transactions for inventory operations. - Maintain an audit trail for
posted transactions and approvals.

Do not implement elaborate enterprise controls at the expense of core
data correctness, but do not knowingly ship trivial security
vulnerabilities.

## 19. V1 test plan

### Inventory tests

-   Stock-in increases location and restaurant balance.
-   Transfer decreases source and increases destination but leaves
    restaurant total unchanged.
-   Consumption decreases stock.
-   Wastage decreases stock and remains distinguishable from
    consumption.
-   Stock count discrepancy creates an adjustment workflow.
-   Corrections do not overwrite original transactions.
-   Duplicate requests do not double-post.

### Import tests

-   Valid Excel/CSV previews correctly.
-   Invalid units and quantities are rejected.
-   Unknown ingredients require mapping.
-   Analysis-only upload creates no ledger event.
-   Closing balance is not interpreted as stock-in.
-   Repeated import is detected or safely idempotent.
-   Approved import posts only eligible rows.

### IoT tests

-   Valid device reading is stored.
-   Duplicate sequence/message is handled.
-   Stale or implausible reading is flagged.
-   Device calibration metadata is retained.
-   Sensor outage does not make manual reconciliation impossible.

### Analytics tests

-   Recipe theoretical usage calculation is correct.
-   Actual-versus-theoretical variance is correct.
-   Sales CSV does not post inventory consumption.
-   Forecast features use no future information.
-   Chronological splits are respected.
-   Metrics handle zero/near-zero actual values safely.

## 20. One-day implementation target

A single day is not enough to complete V1. It can be used to create a
vertical demonstrator if the repository already contains a working
foundation.

A realistic one-day demo target is:

1.  One restaurant and owner/staff login.
2.  Ingredient and storage setup.
3.  Stock-in and consumption ledger workflow.
4.  Excel/CSV upload, preview, and validation.
5.  Recipe and sales CSV calculation for theoretical usage.
6.  A basic dashboard showing actual versus theoretical usage.
7.  One real sensor reading displayed if hardware is already configured.
8.  A baseline forecast demo using available data, labelled preliminary.

Do not claim complete forecasting research, production IoT reliability,
or production readiness from a one-day demo.

## 21. V1 completion criteria

V1 is complete only when:

-   Core inventory transactions are correct and auditable.
-   Location transfers do not alter restaurant total.
-   Excel/CSV import has a review-before-post workflow.
-   Analysis-only uploads cannot change stock.
-   One physical sensor produces stored, timestamped readings with
    calibration metadata.
-   Recipe theoretical usage is calculated from sales and recipe data.
-   Actual usage is calculated from ledger events.
-   Variance is explained and traceable.
-   At least two baselines and one ML candidate are evaluated where data
    volume permits.
-   Evaluation uses chronological validation and reports MAE/RMSE/WAPE
    as appropriate.
-   Real and synthetic data are clearly distinguished.
-   Known limitations are documented.
-   A reproducible demo and experiment report can be produced.

## 22. Research reporting checklist

The final paper/report should include:

1.  Problem statement and motivation.
2.  Related work and gap (supported by reviewed literature).
3.  Proposed architecture and provenance model.
4.  Data sources and collection protocol.
5.  Inventory transaction semantics.
6.  Recipe/BOM calculation method.
7.  IoT hardware, calibration, and measurement error.
8.  Forecast target and feature definitions.
9.  Baseline and ML model configurations.
10. Chronological evaluation design.
11. Metrics and results per ingredient.
12. Ablation/comparison of manual-only and hybrid data where data
    permits.
13. Discrepancy case studies and limitations.
14. Threats to validity and future work.

Do not claim novelty merely because multiple technologies are combined.
The contribution must be stated precisely and supported by experiments.

------------------------------------------------------------------------

## Final implementation rule

**Build the smallest complete system that can produce trustworthy data
and reproducible results.**

The order is:

1.  Audit the current repository.
2.  Fix inventory correctness.
3.  Implement provenance-aware Excel/CSV import.
4.  Capture real IoT readings for one ingredient.
5.  Add recipe and sales analytics.
6.  Implement and evaluate forecasting baselines and one ML model.
7.  Produce results, limitations, and a repeatable demonstration.

The long-term SaaS features remain in the product vision README. They
are not V1 acceptance criteria.

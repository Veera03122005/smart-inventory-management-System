# SmartStock AI

## Complete Project Concept and Technical Handoff

**Purpose:** Product definition, architecture overview, implementation
scope, and development context to share with Claude.

------------------------------------------------------------------------

## 1. Executive Summary

SmartStock AI is an IoT-enabled, AI-powered restaurant inventory
intelligence platform. It helps restaurants monitor ingredient
quantities, record supplier deliveries, reconcile daily stock,
investigate unexplained depletion, and forecast future ingredient
demand.

Traditional restaurant inventory relies on manual counts, spreadsheets,
paper invoices, and staff estimates. These processes can cause
inaccurate stock balances, unexpected shortages, duplicate entries, food
wastage, and poor operational visibility.

SmartStock AI uses a **hybrid inventory model**:

1.  **IoT-enabled inventory:** Load cells measure ingredient-container
    weight.
2.  **Traditional inventory:** Staff record opening stock, supplier
    deliveries, and closing stock.

Both workflows feed one shared backend and authoritative inventory
transaction ledger. The platform also includes supplier and invoice
management, document staging and review, role-based access, alerts,
forecasting, and Manager-led depletion investigation.

**Product positioning:** A restaurant inventory intelligence platform
connecting physical ingredient storage, supplier deliveries, staff
operations, inventory accounting, and predictive analytics.

## 2. Problems Addressed

-   Manual stock counting is time-consuming and error-prone.
-   Staff may not know the actual quantity in storage containers.
-   Supplier-billed quantities may differ from quantities physically
    received.
-   Paper invoices and stock sheets are difficult to consolidate.
-   Ingredients can run out unexpectedly.
-   Expiry risks may go unnoticed.
-   Stock depletion can be incorrectly labelled as consumption or
    wastage.
-   Duplicate records can inflate inventory balances.
-   Managers may lack an audit trail for investigating discrepancies.
-   Historical inventory data may not be used for replenishment
    planning.

## 3. Product Objectives

1.  Monitor ingredient quantities using IoT sensors where available.
2.  Support manual inventory operations for restaurants without IoT.
3.  Maintain accurate and auditable inventory balances.
4.  Record supplier invoices and deliveries without duplicate posting.
5.  Compare billed refill quantities with measured quantities.
6.  Digitize opening and closing stock workflows.
7.  Support document upload, extraction, correction, and verification.
8.  Identify low-stock and expiry risks.
9.  Forecast ingredient demand using historical data.
10. Investigate unexplained depletion without deducting stock twice.
11. Enforce role-based access for Staff, Managers, and Owners.
12. Provide role-appropriate operational and financial reports.

## 4. User Roles and Permissions

Backend authorization is mandatory. Hiding frontend buttons or routes is
not sufficient.

### Owner

Full restaurant-level governance and financial access:

-   Full dashboard.
-   Sales and revenue.
-   Purchase costs and ingredient unit costs.
-   Stock valuation.
-   Profit and food-cost analytics where supported by reliable data.
-   Manager and Staff account administration.
-   Supplier and inventory configuration.
-   Stock, alert, IoT, and refill monitoring.
-   Operational and financial reports.
-   Audit history and investigation records.

### Manager

Operational management with sales visibility, but without Owner-level
cost and profit access:

-   Sales figures and sales reports.
-   Inventory and stock monitoring.
-   Opening and closing submission monitoring.
-   Depletion investigation and wastage classification.
-   Supplier delivery and invoice monitoring.
-   IoT device and refill-variance monitoring.
-   Staff account creation, deactivation, reactivation, and management.
-   Operational reports and alerts.

Restrictions:

-   No purchase-cost or ingredient unit-cost access.
-   No stock valuation.
-   No gross profit, net profit, margins, or food-cost valuation.
-   Cannot create or promote a user to Owner.
-   Cannot modify Manager or Owner accounts.
-   Cannot change their own role.

### Staff

Daily inventory operations:

-   Opening-stock entry.
-   Supplier delivery entry.
-   Invoice and stock-sheet upload.
-   Review and correction of their own staged documents.
-   Verification and posting of valid submissions.
-   Closing-stock entry.
-   Barcode scanning and permitted IoT refill operations.
-   Operational stock, alerts, and own submission history.

Restrictions:

-   No sales or revenue access.
-   No purchase-cost analytics or stock valuation.
-   No Manager or Owner endpoints.
-   No wastage classification.
-   No user administration.
-   No direct editing of posted ledger transactions.
-   No access to another Staff member's staged documents.

  Capability                     Staff   Manager                   Owner
  ---------------------------- ------- --------- -----------------------
  Operational inventory            Yes       Yes                     Yes
  Opening/closing stock            Yes   Monitor                     Yes
  Supplier delivery entry          Yes   Monitor                     Yes
  Sales reports                     No       Yes                     Yes
  Purchase-cost analytics           No        No                     Yes
  Stock valuation                   No        No                     Yes
  Profit and margins                No        No                     Yes
  Depletion investigation           No       Yes         View/governance
  Wastage classification            No       Yes   Controlled governance
  Staff account management          No       Yes                     Yes
  Manager account management        No        No                     Yes

## 5. System Architecture

### Conceptual layers

1.  **Physical layer:** ESP32, HX711, load cell, ingredient containers,
    barcode labels/scanner, Wi-Fi.
2.  **Data collection:** Sensor telemetry, barcode identification,
    manual counts, supplier entries, uploaded documents.
3.  **Application/backend:** Flask REST API, authentication, business
    rules, inventory ledger, audit logging.
4.  **Intelligence:** Demand forecasting, inventory-risk classification,
    reorder recommendations, rule-based alerts.
5.  **User interface:** Owner dashboard, Manager dashboard, Staff
    workspace, inventory screens, IoT monitoring, reports.

### Technology stack

  Layer                    Technology
  ------------------------ ----------------------------
  Frontend                 React 18, TypeScript, Vite
  Styling                  Tailwind CSS
  Icons                    Lucide React
  Backend                  Python, Flask, REST API
  Current database         SQLite
  Future database option   PostgreSQL / Supabase
  IoT                      ESP32, HX711, load cell
  ML                       Scikit-learn, XGBoost
  Data processing          Pandas, NumPy
  Document parsing         CSV, XLSX, PDF parsing
  Image validation         Pillow
  Authentication           JWT and role-based access
  Communication            Wi-Fi, HTTP/REST

**Architecture status:** The current implementation uses SQLite.
PostgreSQL/Supabase is a possible future deployment option, not an
assumed current feature.

## 6. Core Product Modules

### 6.1 Inventory Management

Each ingredient should have:

-   Ingredient ID and name.
-   Category.
-   Authoritative inventory unit.
-   Current stock balance.
-   Minimum stock and reorder thresholds.
-   Supplier information.
-   Batch number and expiry date where applicable.
-   Storage location.
-   Barcode.
-   IoT monitoring status, if applicable.

Example:

  Ingredient      Current stock   Minimum stock Status
  ------------- --------------- --------------- -----------
  Chicken                  8 kg           10 kg Low stock
  Tomatoes                18 kg            5 kg Normal
  Cooking oil               3 L             5 L Low stock
  Onions                  24 kg            8 kg Normal

Inventory balances must derive from the authoritative transaction ledger
and its balance projection. Frontend screens must not independently
overwrite quantities.

### 6.2 IoT-Based Inventory Monitoring

**Hardware:**

-   ESP32 microcontroller.
-   HX711 load-cell amplifier.
-   Load cell (initial prototype: 20 kg).
-   Ingredient container.
-   Barcode label.
-   Wi-Fi connection.

**Telemetry flow:**

1.  Load cell measures ingredient-container weight.
2.  HX711 amplifies and digitizes the sensor signal.
3.  ESP32 reads the sensor value.
4.  ESP32 sends telemetry to Flask.
5.  Backend validates device identity and active inventory association.
6.  Raw readings are stored.
7.  The interface displays the latest reliable measurement.

Sensor readings must be validated for stability, freshness, calibration,
and connectivity. Stale or unstable readings must not be presented as
reliable current measurements.

**Barcode-based refill workflow:**

1.  Staff scans the ingredient/container barcode.
2.  Staff enters supplier-billed weight and billed price.
3.  System captures stable pre-refill weight.
4.  Staff refills the container.
5.  System captures stable post-refill weight.
6.  System calculates measured refill quantity.
7.  System compares measured and billed quantities.
8.  System stores the variance for investigation.

`Measured Refill = Post-Refill Weight - Pre-Refill Weight`

`Variance = Measured Refill - Billed Weight`

Retain billed and measured quantities separately.

**Accounting distinction:**

-   Supplier receipt: `STOCK_IN`, increases consolidated restaurant
    stock.
-   Internal container refill: `REFILL`, zero consolidated inventory
    effect.

A container refill must not increase total restaurant stock a second
time.

### 6.3 Traditional Inventory Workflow

The traditional workflow must work without IoT and feed the same
inventory ledger.

**Morning --- Opening stock**

1.  Staff selects business date.
2.  Staff records physical opening quantities.
3.  Staff may enter values manually or upload a stock sheet.
4.  System validates missing, invalid, negative, and duplicate entries.
5.  Staff reviews and verifies.
6.  Valid submission is posted.
7.  Physical opening is compared with current book balance.
8.  Any discrepancy is recorded through an auditable adjustment.

**During the day --- Supplier deliveries**

Record supplier, invoice number/date, ingredient, billed quantity/unit,
unit price, batch number, and expiry date.

One invoice may contain multiple ingredients and multiple batches of the
same ingredient. Verified deliveries post `STOCK_IN` exactly once.

**Evening --- Closing stock**

1.  Staff records physical closing quantities.
2.  Staff reviews and verifies.
3.  System calculates available stock.
4.  System calculates daily depletion.
5.  System posts reconciliation once.
6.  System records unexplained depletion for Manager investigation.

`Available Stock = Opening Stock + Verified Deliveries`

`Daily Depletion = Opening Stock + Verified Deliveries - Physical Closing Stock`

Positive depletion is not automatically proof of food consumption or
wastage.

### 6.4 Document Management and Review

Intended supported formats:

-   CSV.
-   XLS/XLSX.
-   PDF.
-   JPG/JPEG.
-   PNG.

Workflow:

`UPLOAD → PARSE → STAGE → REVIEW → CORRECT → VERIFY → POST`

Requirements:

-   Upload must not modify inventory.
-   Extracted information remains a draft.
-   Staff reviews and corrects extracted values.
-   Explicit verification is required before posting.
-   Original files and hashes are retained.
-   Duplicate uploads are detected.
-   Invalid, unsupported, oversized, or corrupted files are rejected.
-   Staff ownership is enforced.
-   Posted documents cannot be edited through ordinary review.

**Current limitation:** Image OCR is not implemented. JPG/PNG uploads
are validated but require manual data entry. Do not claim scanned images
are automatically read.

### 6.5 Supplier and Invoice Management

-   Supplier records.
-   Invoice headers.
-   Multi-ingredient invoices.
-   Multiple batches of the same ingredient.
-   Billed quantity and unit.
-   Unit price and line total, subject to role redaction.
-   Batch and expiry tracking.
-   Unit normalization.
-   Duplicate invoice prevention.
-   Delivery history.

Example:

  Ingredient       Batch        Billed quantity Expiry
  ---------------- ---------- ----------------- --------
  Chicken Breast   BATCH-A1                5 kg 25 Dec
  Chicken Breast   BATCH-A2              7.5 kg 28 Dec

Both lines must be independently retained.

### 6.6 Unit Normalization

Inventory movements must use the ingredient's authoritative inventory
unit.

Supported examples:

-   kg ↔ g.
-   L ↔ ml.

Examples:

-   5,000 g billed for an ingredient whose inventory unit is kg becomes
    +5 kg.
-   750 ml billed for an ingredient whose inventory unit is L becomes
    +0.75 L.

Requirements:

-   Preserve original billed quantity and unit.
-   Store normalized inventory quantity separately.
-   Reject incompatible and unknown units.
-   Do not perform mass-to-volume conversion without validated
    ingredient-specific density.
-   Use consistent units across opening counts, deliveries, closing
    counts, IoT readings, and ledger balances.

### 6.7 AI-Powered Demand Forecasting

Proposed algorithms:

  Algorithm           Intended use
  ------------------- ----------------------------------------------
  XGBoost             Ingredient demand forecasting
  Random Forest       Inventory status/risk classification
  Rule-based engine   Low-stock, expiry and reorder alerts
  Isolation Forest    Potential future anomaly-detection extension

Potential inputs:

-   Historical ingredient depletion.
-   Day of the week.
-   Historical demand patterns.
-   Seasonal patterns where data is sufficient.
-   Supplier delivery history.
-   Verified sales-to-ingredient mappings, if available.

Example:

  Ingredient      Forecast demand   Available stock Recommendation
  ------------- ----------------- ----------------- ----------------
  Chicken                   15 kg              8 kg Reorder
  Tomatoes                  10 kg             18 kg Sufficient
  Cooking oil                 5 L               3 L Reorder

Forecasts must identify their prediction period and communicate
uncertainty where possible. They are not guaranteed demand or confirmed
purchase orders.

**Data limitation:** Recipe-level ingredient demand requires validated
recipe/BOM data and POS sales quantities mapped to ingredients. Do not
claim automatic consumption inference without those integrations.

### 6.8 Alerts and Notifications

Alert categories:

-   Low stock and critical stock.
-   Near-expiry and expired ingredients.
-   Unstable or stale sensor readings.
-   IoT device disconnection.
-   Refill variance.
-   Unexplained depletion.
-   Document extraction failure.
-   Duplicate invoice attempts.
-   Pending Manager investigation.

Each alert should include severity, timestamp, ingredient/device, source
event, description, recommended action, and acknowledgement status where
applicable.

### 6.9 Depletion Investigation and Wastage Classification

This is the planned Manager workflow.

Closing reconciliation has already accounted for physical depletion.
Manager classification must therefore be a zero-sum reclassification
event.

Example:

-   Opening stock: 20 kg.
-   Supplier delivery: 10 kg.
-   Closing stock: 22 kg.
-   Total depletion: 8 kg.

Manager classifies:

  Category                           Quantity
  -------------------------------- ----------
  Spoilage                               2 kg
  Preparation loss                       1 kg
  Spillage                               1 kg
  Normal operational consumption         4 kg
  Total                                  8 kg

Classification must not create another negative stock movement.

`Inventory Delta for Classification = 0`

Categories:

-   Spoilage.
-   Expired.
-   Preparation loss.
-   Spillage.
-   Damaged ingredients.
-   Theft or suspected unauthorized removal.
-   Measurement/counting error.
-   Normal operational consumption.
-   Other/unexplained.

Manager must be able to investigate, add notes, split quantities across
categories, partially classify, or leave a record unresolved.

`Classified Quantity <= Total Eligible Depletion`

`Remaining Unclassified = Total Depletion - Classified Quantity`

Classification events must be atomic, idempotent, immutable after
posting, and auditable. Corrections require controlled
reversal/reclassification events.

### 6.10 Reports and Analytics

**Owner reports:**

-   Stock valuation.
-   Purchase costs.
-   Sales and revenue.
-   Profit and food-cost analytics where reliable data exists.
-   Supplier purchasing history.
-   Wastage valuation.
-   Inventory movement trends.
-   User and audit history.

**Manager reports:**

-   Sales overview.
-   Daily stock movement.
-   Low-stock ingredients.
-   Expiry risks.
-   Depletion by ingredient.
-   Wastage quantity by category.
-   Unresolved investigations.
-   Supplier delivery history.

Managers must not receive purchase-cost or profit analytics.

**Staff reports:**

-   Operational stock status.
-   Opening and closing history.
-   Own delivery submissions.
-   Own document submissions.
-   Operational alerts.

## 7. Inventory Accounting and Ledger Design

All stock-changing events must use one authoritative, auditable
inventory transaction ledger.

  Transaction                                   Inventory effect
  -------------------- -----------------------------------------
  `STOCK_IN`                                            Positive
  `CONSUMPTION`                                         Negative
  `ADJUSTMENT`                              Positive or negative
  `WASTAGE`              Negative only when directly posted once
  `REFILL`                              Zero consolidated effect
  `RECLASSIFICATION`                                        Zero
  `REVERSAL`                    Opposite of original transaction

Mandatory rules:

1.  Supplier receipt increases consolidated stock exactly once.
2.  Internal container refill does not increase consolidated stock.
3.  Opening physical discrepancies are explicitly reconciled.
4.  Closing reconciliation accounts for depletion exactly once.
5.  Manager wastage classification does not deduct stock a second time.
6.  Posted ledger transactions are immutable.
7.  Corrections use reversal and replacement transactions.
8.  Posting operations are atomic.
9.  Idempotency prevents duplicate posting.
10. Balance projections remain consistent with the ledger.

**Opening-to-closing example:**

Previous closing balance: 20 kg.\
Current morning physical opening: 18 kg.\
Supplier delivery: +10 kg.\
Evening physical closing: 22 kg.

  Event                   Movement   Balance
  --------------------- ---------- ---------
  Previous closing             ---     20 kg
  Opening discrepancy        -2 kg     18 kg
  Supplier delivery         +10 kg     28 kg
  Daily depletion            -6 kg     22 kg

Final balance: 22 kg.

**Double-deduction prevention:** If closing reconciliation has posted -8
kg, a later classification of 2 kg as spoilage must not post another -2
kg. It explains part of the original depletion without changing
inventory again.

## 8. Main Database Entities

This is a conceptual entity list. Inspect the actual schema before
implementing migrations; the list does not imply every table is already
implemented.

  Entity/table                  Purpose
  ----------------------------- -------------------------------------
  `users`                       Staff, Manager and Owner accounts
  `ingredients`                 Ingredient master
  `categories`                  Ingredient categorization
  `suppliers`                   Supplier records
  `supplier_invoices`           Invoice headers
  `supplier_invoice_items`      Invoice lines and batches
  `inventory_transactions`      Authoritative inventory ledger
  `inventory_balances`          Current balance projection
  `daily_stock_counts`          Opening and closing observations
  `depletion_logs`              Unclassified daily depletion
  `depletion_classifications`   Manager classification history
  `storage_units`               Ingredient storage locations
  `iot_devices`                 ESP32 device registry
  `iot_readings`                Sensor telemetry
  `refill_sessions`             Internal refill records
  `document_uploads`            Original files and staged data
  `alerts`                      Operational alerts
  `ai_predictions`              Forecast and classification results
  `reorder_recommendations`     Suggested replenishment
  `audit_log`                   User and system activity

## 9. End-to-End Restaurant User Journey

1.  **Restaurant setup:** Owner configures ingredients, suppliers,
    storage locations, thresholds, devices, Managers, and Staff.
2.  **Opening stock:** Staff records physical opening quantities. System
    compares counts with book balances and records discrepancies.
3.  **Supplier deliveries:** Staff enters or uploads invoices. Verified
    deliveries post stock-in movements.
4.  **Kitchen operations:** Ingredients are used throughout the day. IoT
    devices monitor configured containers; traditional workflows cover
    non-IoT ingredients.
5.  **Container refill:** Staff scans barcode, enters billed quantity
    and price, and captures pre/post-refill sensor readings.
6.  **Closing stock:** Staff records physical closing quantities. System
    reconciles the ledger and calculates depletion.
7.  **Manager investigation:** Manager investigates unexplained
    depletion and classifies verified losses without double deduction.
8.  **AI forecasting:** System uses available historical data to
    estimate future demand and suggest replenishment.
9.  **Owner review:** Owner reviews operations, sales, purchase costs,
    stock valuation, and supported financial reports.

## 10. Product Differentiators

1.  Hybrid inventory tracking for IoT-enabled and traditional
    restaurants.
2.  Physical weight measurement for configured ingredient containers.
3.  Billed-versus-measured refill comparison.
4.  Unified inventory ledger for manual and IoT workflows.
5.  Document-assisted operations with review-before-post.
6.  Controlled depletion classification that avoids double deduction.
7.  Demand forecasting based on historical data.
8.  Role-based governance for Staff, Manager, and Owner.

## 11. Development Roadmap

### V1 --- Core product

-   Authentication and role-based access.
-   Inventory management.
-   Traditional opening, delivery, and closing workflows.
-   Supplier invoice tracking.
-   Document staging and review.
-   IoT telemetry and refill infrastructure.
-   Demand forecasting.
-   Alerts and reports.

### V1 completion stages

-   Phase 1: Role-based permissions and financial data redaction.
-   Phase 2: Staff opening, deliveries, closing, and document review.
-   Phase 2.1: Critical accounting, ownership, multi-batch,
    unit-conversion, and document corrections.
-   Phase 3: Manager depletion investigation and zero-sum wastage
    classification.
-   Phase 4: IoT billed weight, billed price, and sensor variance.
-   Final: Security, accounting, hardware, and end-to-end regression
    validation.

### V2 --- Advanced intelligence

Potential extensions:

-   OCR for scanned invoices and stock sheets.
-   Multi-restaurant and multi-branch support.
-   Advanced anomaly detection.
-   Automated supplier purchase-order suggestions.
-   POS integration.
-   Recipe/BOM-based consumption analysis.
-   Mobile application.
-   Supplier integrations.

### V3 --- Broader restaurant operations platform

Long-term possibilities:

-   Recipe and menu cost management.
-   Kitchen production planning.
-   Staff scheduling.
-   Food safety and hygiene checklists.
-   Equipment maintenance.
-   Waste-reduction analytics.
-   Advanced business intelligence.

These are future extensions, not assumed V1 capabilities.

## 12. Current Implementation Status and Honest Limitations

The following status reflects project reports supplied during
development. These reports were generated by the local development agent
and have not been independently audited in this document.

  -----------------------------------------------------------------------
  Area                                Reported status
  ----------------------------------- -----------------------------------
  Phase 1 role-based access and       Reported complete
  financial redaction                 

  Phase 2 traditional workflows       Reported complete

  Phase 2.1 critical defect           Reported complete
  corrections                         

  Phase 3 Manager depletion           Pending
  investigation                       

  Phase 4 enhanced IoT refill billing Pending
  and variance                        

  Image OCR                           Not implemented

  Physical ESP32/HX711 validation     Must be demonstrated separately

  POS-to-ingredient mapping           Not established

  Recipe/BOM-based automatic          Not established
  consumption                         

  Multi-restaurant SaaS deployment    Future extension
  -----------------------------------------------------------------------

### Claims discipline

Do not claim a feature is production-ready merely because a UI screen
exists or a test suite passes.

-   Physical IoT operation must be validated with actual hardware.
-   Sensor calibration and measurement accuracy must be measured.
-   Forecast quality must be evaluated on appropriate historical test
    data.
-   Image OCR must not be claimed until actual OCR extraction is
    implemented.
-   Automatic food consumption must not be claimed without validated
    recipe/BOM and POS mappings.
-   Profit and food-cost calculations require reliable sales and cost
    data.
-   Multi-restaurant support requires tenant isolation and additional
    authorization design.

## 13. Quality, Security, and Reliability Requirements

### Security

-   Enforce permissions at the backend.
-   Redact financial fields in API serialization.
-   Validate active-account status on protected requests.
-   Prevent privilege escalation.
-   Enforce Staff document ownership.
-   Protect original uploaded files.
-   Validate file size, content type, and file signatures.
-   Prevent path traversal.
-   Do not expose credentials or secrets in source code.

### Data integrity

-   Use transactions for multi-step inventory posting.
-   Use deterministic idempotency keys.
-   Preserve historical data.
-   Make posted ledger movements immutable.
-   Correct errors through reversal and replacement events.
-   Maintain balance-to-ledger consistency.
-   Prevent duplicate invoice and document posting.
-   Validate units before inventory posting.

### Testing

Each implementation phase should include:

-   Backend unit and API tests.
-   Role-based authorization tests.
-   Ledger integrity tests.
-   Migration tests.
-   Idempotency and duplicate-posting tests.
-   Frontend type checking.
-   Production build.
-   Browser acceptance tests.
-   Database backup and historical-data verification.

### Engineering discipline for future work

-   Inspect existing source code before modifying it.
-   Inspect actual database schema and migrations before designing
    migrations.
-   Do not blindly apply proposed schema changes.
-   Preserve uncommitted user work.
-   Do not reset or overwrite the working tree.
-   Do not claim tests passed unless they were actually executed.
-   Report exact files modified, test commands, results, limitations,
    and Git status.
-   Implement only the authorized phase and stop for review before
    proceeding.

## 14. Final Product Vision

SmartStock AI aims to make restaurant ingredient inventory more
measurable, traceable, and predictable.

It connects:

-   Physical ingredient storage.
-   IoT weight sensing.
-   Barcode-based refill operations.
-   Supplier invoices and deliveries.
-   Staff opening and closing workflows.
-   A centralized inventory ledger.
-   Manager investigation and wastage classification.
-   Machine Learning demand forecasting.
-   Role-based dashboards and reports.

The core value is not simply recording how much stock a restaurant has.
It is establishing **where inventory came from, how it moved, what
quantity remains, how discrepancies are explained, and what the
restaurant may need next**.

The recommended strategy is to complete and validate the core V1
workflows before expanding into POS integration, recipe management,
staff scheduling, or broader ERP functionality.

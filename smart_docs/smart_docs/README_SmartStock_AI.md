# SmartStock AI --- Product Vision

> **Long-term product specification for a multi-restaurant inventory,
> IoT, document intelligence, analytics, and independent POS platform.**

## Product vision and delivery strategy

SmartStock AI has two connected but distinct goals:

1.  **Research prototype (V1):** prove a focused technical contribution
    using real or clearly labelled pilot data. The immediate priority is
    inventory correctness, provenance-aware data capture, demand
    forecasting, and discrepancy analytics.
2.  **Commercial product (future):** expand the validated foundation
    into a multi-restaurant SaaS platform with broader role management,
    document automation, IoT support, independent POS, offline PWA
    workflows, and production operations.

Do not mistake the long-term product scope below for the V1 delivery
commitment. V1 is intentionally narrower. Features not listed in the V1
specification are future scope unless explicitly approved.

### Document set

-   `README_SmartStock_AI.md` --- long-term product vision and
    architecture.
-   `V1_Research_and_Implementation_Spec.md` --- immediate build scope,
    research question, experiment plan, acceptance criteria, and
    deferred features.

### V1 priority

The immediate prototype should demonstrate a complete, testable
workflow:

1.  Capture stock movements in a ledger.
2.  Import Excel/CSV records through a review-before-post process.
3.  Capture actual readings from one load-cell/ESP32 prototype for one
    selected ingredient.
4.  Compare theoretical ingredient usage from recipe quantities and
    sales data with actual recorded usage.
5.  Compare forecasting baselines against a machine-learning model using
    time-based evaluation.
6.  Preserve provenance so measured, manually entered, imported, and
    predicted values are not confused.

### Research boundary

The research contribution is not simply "using AI for inventory." The
testable question is:

**Can provenance-aware hybrid inventory data improve restaurant
ingredient demand forecasting and operational discrepancy detection
compared with conventional historical inventory data?**

The V1 specification defines the target variable, candidate models,
baselines, evaluation metrics, data requirements, and limitations.
Claims must be supported by recorded experiments; simulated data must be
labelled and must not be presented as real restaurant evidence.

------------------------------------------------------------------------

# SmartStock AI

> **AI-assisted, multi-restaurant inventory management with IoT
> monitoring, document intelligence, operational analytics, and an
> independent POS module.**

SmartStock AI is designed for restaurant owners operating one or more
restaurants with different inventory practices. One restaurant may use
ESP32/load-cell monitoring for selected ingredients; another may
maintain paper registers, Excel workbooks, and PDF reports. Both use one
application, a shared inventory domain, and auditable workflows.

**Document status:** This README describes the intended end-to-end
product and recommended engineering architecture. It is a product
specification, not proof that every feature is already implemented in
the current repository. Verify implementation status against source code
and reproducible tests.

## Contents

1.  [Vision and scope](#1-vision-and-scope)
2.  [Problems and product
    principles](#2-problems-and-product-principles)
3.  [Users and permissions](#3-users-and-permissions)
4.  [Restaurant operating models](#4-restaurant-operating-models)
5.  [End-to-end workflows](#5-end-to-end-workflows)
6.  [Inventory domain and ledger
    rules](#6-inventory-domain-and-ledger-rules)
7.  [Document intelligence](#7-document-intelligence)
8.  [IoT monitoring](#8-iot-monitoring)
9.  [Barcode workflows](#9-barcode-workflows)
10. [AI and analytics](#10-ai-and-analytics)
11. [Independent POS](#11-independent-pos)
12. [Multi-tenant architecture](#12-multi-tenant-architecture)
13. [Recommended technology
    architecture](#13-recommended-technology-architecture)
14. [Conceptual data model](#14-conceptual-data-model)
15. [API design](#15-api-design)
16. [Security](#16-security)
17. [Mobile PWA and offline
    behavior](#17-mobile-pwa-and-offline-behavior)
18. [Reliability and observability](#18-reliability-and-observability)
19. [Testing and acceptance
    criteria](#19-testing-and-acceptance-criteria)
20. [Implementation roadmap](#20-implementation-roadmap)
21. [Suggested repository structure](#21-suggested-repository-structure)
22. [Local development](#22-local-development)
23. [Configuration](#23-configuration)
24. [Deployment](#24-deployment)
25. [Explicit exclusions](#25-explicit-exclusions)
26. [Definition of done](#26-definition-of-done)
27. [Implementation status](#27-implementation-status)

------------------------------------------------------------------------

## 1. Vision and scope

SmartStock AI is a **multi-tenant restaurant inventory and operations
platform** centered on inventory accuracy, traceability, and useful
operational intelligence.

It supports:

-   Multiple restaurants managed by one owner.
-   Restaurant-scoped managers and staff.
-   IoT-assisted inventory monitoring for selected ingredients and
    storage positions.
-   Traditional paper-based inventory workflows.
-   Manual and barcode-assisted stock-in and container refill.
-   Stock counts, transfers, consumption, wastage, and adjustments.
-   Camera capture and upload of images, PDFs, Excel workbooks, and CSV
    files.
-   OCR, table extraction, staff verification, and controlled inventory
    imports.
-   AI-assisted usage analysis, anomaly explanations, and demand
    forecasting.
-   An independent POS and revenue module.
-   A mobile-first Progressive Web App (PWA).

A restaurant may combine IoT and manual tracking. Tracking configuration
therefore belongs at the appropriate level---restaurant, ingredient, and
storage location---not simply to one global restaurant flag.

### Product outcome

The platform should help users answer:

-   What stock do we have, and where is it stored?
-   How did each balance change?
-   Who recorded, reviewed, or approved a change?
-   Did the data originate from a manual form, barcode, document, or IoT
    device?
-   Which values are measured, reported, extracted, estimated, or
    predicted?
-   What is likely to run low, and how reliable is the forecast?
-   How do restaurants compare, and what is the consolidated position?

## 2. Problems and product principles

Restaurant inventory information is often fragmented across paper
registers, spreadsheets, manual calculations, and disconnected devices.
Different channels can disagree or record the same physical event more
than once. Owners may also lack a trustworthy consolidated view.

SmartStock AI addresses these problems using one common inventory domain
and controlled capture workflows.

### Non-negotiable product principles

1.  **One platform, role-specific experiences.** Do not create separate
    account systems for IoT and traditional staff. Use one identity and
    authorization model; vary dashboards and capabilities.
2.  **One authoritative inventory ledger.** Posted transactions are the
    source of truth. Balances are projections that must reconcile to the
    ledger.
3.  **Measurement method and capture channel are different concepts.**
4.  **AI assists; deterministic backend rules validate and post.**
5.  **No silent corrections.** A mismatch creates a discrepancy/review
    item; it must not overwrite the ledger.
6.  **Every important operation is auditable.**
7.  **A frontend control is not a security boundary.** The backend
    enforces all permissions and tenant scope.

Suggested measurement methods: `IOT`, `MANUAL`, `HYBRID`.

Suggested capture channels: `MANUAL_FORM`, `BARCODE`, `DOCUMENT_SCAN`,
`EXCEL_IMPORT`, `PDF_IMPORT`, `IOT_INGESTION`.

## 3. Users and permissions

### Owner

An owner can manage multiple restaurants and can:

-   Create and manage restaurants.
-   Invite and assign managers and staff.
-   View consolidated and restaurant-specific dashboards.
-   Review inventory, wastage, alerts, valuation, and audit history.
-   Access permitted POS revenue analytics.
-   Compare performance across authorized restaurants.
-   Review sensitive adjustments.

Owners are not expected to perform routine kitchen refills or daily
stock counts. Exceptional operational access, if allowed, must be
explicit and audited.

### Manager

A manager is assigned to exactly one restaurant in the initial product
model. A manager can:

-   Oversee day-to-day restaurant inventory operations.
-   Review stock-in records, counts, and discrepancies.
-   Monitor IoT devices when enabled.
-   Review document-import exceptions.
-   Review staff activity and restaurant reports.
-   Perform authorized adjustments within configured limits.

A manager cannot create restaurants, change their own assignment, or
access another restaurant.

### Staff

Staff are assigned to one restaurant and receive a task-focused
dashboard. Depending on permissions and restaurant configuration, staff
can:

-   Scan ingredient/container barcodes.
-   Record authorized stock-in, refills, counts, and wastage.
-   Capture paper registers.
-   Upload Excel, CSV, and PDF files.
-   Review and correct extracted values.
-   Verify and approve their submissions where policy permits.
-   View their activity history.

Staff cannot manage memberships, access other restaurants, or view
owner-level consolidated financial analytics.

### Action-based permissions

Use explicit permissions rather than relying only on broad role names.
Examples:

``` text
inventory.stock_in.create
inventory.stock_in.approve
inventory.refill.create
inventory.stock_count.submit
inventory.adjustment.create
inventory.adjustment.approve
documents.upload
documents.review
documents.approve
documents.post
iot.read
iot.device.manage
reports.restaurant.read
reports.consolidated.read
restaurants.manage
memberships.manage
pos.orders.manage
pos.reports.read
```

Enforce permissions in backend services on every protected request. For
high-risk adjustments, use separation of duties: the person who submits
the adjustment may need a different authorized reviewer.

## 4. Restaurant operating models

### IoT-enabled restaurant staff experience

Show only capabilities enabled for the user's restaurant and assigned
work:

-   Sensor status, latest reading, and last-seen time.
-   Ingredient/container monitoring.
-   Low-stock and abnormal-reading alerts.
-   Barcode-assisted container refill.
-   Manual stock-in and physical stock verification.
-   Wastage reporting and activity history.

A load cell measures weight at a physical position. It does not
inherently know whether a change represents consumption, refill,
removal, container movement, cleaning, or sensor noise. The system needs
configuration and validated event logic.

### Traditional restaurant staff experience

Provide:

-   Camera capture of opening/closing registers.
-   Usage and wastage sheet scanning.
-   Excel workbook and CSV upload.
-   PDF upload, including scanned PDFs.
-   Extracted table review and ingredient matching.
-   Correction and approval workflow.
-   Manual stock-in, stock counts, usage, and wastage.
-   Discrepancy and processing history.

### Mixed operating model

A restaurant may use IoT for rice and oil, but manual tracking for
vegetables and spices. Another restaurant may use paper records for
nearly all ingredients.

Configure the method by restaurant + ingredient + storage location. The
backend returns the effective capabilities to the frontend. The frontend
may hide irrelevant actions for usability, but backend authorization
remains mandatory.

## 5. End-to-end workflows

### 5.1 Onboarding

1.  Owner registers or is provisioned.
2.  Owner creates a restaurant.
3.  Owner configures storage locations, units, categories, and
    ingredients.
4.  Owner configures tracking method per ingredient/location.
5.  Owner registers IoT devices where required.
6.  Owner invites manager and staff.
7.  Users accept invitations and receive restaurant-scoped memberships.
8.  Backend resolves access from trusted membership records.

Never trust a `restaurant_id` supplied by the browser as proof of
authorization.

### 5.2 Stock-in

Stock-in means incoming stock entering restaurant inventory; it is not a
purchase-order workflow.

1.  Authorized user opens Stock-in.
2.  User selects or scans the ingredient.
3.  User selects destination storage location.
4.  User enters quantity and unit.
5.  User enters batch, expiry, and unit cost when available and
    applicable.
6.  User supplies source/reference and reason if required.
7.  Backend validates permissions, restaurant scope, ingredient,
    location, units, quantity, and idempotency key.
8.  Backend posts the transaction atomically.
9.  Balance projection and audit history are updated.

A barcode identifies an ingredient/container; it does not establish
quantity, batch, expiry, or cost by itself.

### 5.3 Container refill

A refill moves stock internally from bulk storage to a kitchen
container.

1.  Staff scans the container barcode.
2.  Backend resolves the ingredient and destination location.
3.  Staff confirms the refill operation and quantity/measurement
    evidence.
4.  Backend validates source availability and permissions.
5.  Backend posts paired location effects atomically.
6.  Source and destination balances update.
7.  Audit history records user, time, source, destination, and evidence.

**A refill must not increase consolidated restaurant stock.**

### 5.4 Stock count

1.  Staff starts a count for a defined restaurant/location.
2.  System records the expected balance snapshot.
3.  Staff records physical quantity.
4.  Backend considers the snapshot and intervening transactions.
5.  Differences are displayed and reasons collected.
6.  Authorized reviewer approves adjustments when required.
7.  Backend posts a correction transaction; it never erases ledger
    history.

### 5.5 Usage and wastage

Keep these separate:

-   `CONSUMPTION`: ingredient used in normal operations.
-   `WASTAGE`: ingredient spoiled, damaged, discarded, or otherwise
    lost.

Record quantity, unit, location, timestamp, reason, source, and actor.
Prevent duplicate usage being posted through both IoT interpretation and
a paper/manual record.

### 5.6 Owner analytics

1.  Owner opens consolidated dashboard.
2.  Backend aggregates only restaurants the owner is authorized to
    access.
3.  Owner drills into an individual restaurant.
4.  Reports distinguish posted facts from estimates and predictions.
5.  Drill-downs link to underlying transactions and source evidence.

## 6. Inventory domain and ledger rules

### 6.1 Location-aware inventory

An ingredient can exist in bulk storage, refrigerator, freezer, kitchen
container, or preparation area. Track both location balances and
consolidated restaurant balances.

### 6.2 Canonical transaction semantics

  ---------------------------------------------------------------------
  Transaction          Meaning               Effect on restaurant total
  -------------------- -------------------- ---------------------------
  `STOCK_IN`           Incoming stock                          Increase
                       enters restaurant    

  `TRANSFER_OUT`       Stock leaves one             No change by itself
                       internal location    

  `TRANSFER_IN`        Stock enters another         No change by itself
                       internal location    

  `CONSUMPTION`        Ingredient used                         Decrease

  `WASTAGE`            Ingredient                              Decrease
                       lost/discarded       

  `ADJUSTMENT_IN`      Approved correction                     Increase
                       upward               

  `ADJUSTMENT_OUT`     Approved correction                     Decrease
                       downward             
  ---------------------------------------------------------------------

Represent an internal transfer as one logical operation with paired
location effects committed atomically. The two legs cancel at
restaurant-total level.

### 6.3 Balance equation

For an ingredient and defined scope:

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

A paper closing balance is a snapshot, not a stock-in transaction.

### 6.4 Ledger integrity

-   Posted ledger events are append-only from the business perspective.
-   Corrections use reversal/correction transactions referencing the
    original.
-   Balance projections can be rebuilt from the ledger.
-   Ledger writes and balance updates must be atomic or recoverable
    using a reliable outbox/reconciliation design.
-   Every write has a stable transaction ID and idempotency key.
-   Protect against concurrent writes using database constraints and
    suitable transaction isolation.

### 6.5 Quantity, units, batches, and valuation

-   Use exact decimal arithmetic or integer-scaled base units; never
    binary floating point for stock or money.
-   Define canonical base units and explicit conversions.
-   Reject ambiguous or unsupported conversions.
-   Preserve entered and normalized quantities where auditability
    requires it.
-   Support batch/lot and expiry where relevant.
-   FEFO can guide physical picking for perishables. Financial valuation
    (FIFO or weighted average) is a separate policy decision.
-   If unit cost is missing, mark valuation incomplete/estimated. Never
    invent cost.

### 6.6 Cross-channel duplicate prevention

One physical event may appear in IoT readings, a barcode operation, a
manual entry, and a paper register. Use idempotency keys, source
references, duplicate fingerprints, and reconciliation review.
Similarity is a signal, not sufficient proof to silently discard a
record.

## 7. Document intelligence

### 7.1 Two explicit upload purposes

**Analysis-only** - Extract and summarize. - Compare periods. - Find
trends, anomalies, missing values, and potential errors. - Produce a
report. - Never create inventory transactions.

**Inventory import** - Extract eligible stock movement/count records. -
Match ingredients and units. - Show source evidence and a review
screen. - Require authorized verification. - Validate against existing
ledger data. - Post only approved eligible transactions.

Uploading a file must never automatically change inventory.

### 7.2 Supported source formats

-   `.xlsx`
-   `.xls` only if the chosen parser supports it safely
-   `.csv`
-   Text-based PDF
-   Scanned/image-based PDF
-   Camera-captured JPEG, PNG, or WebP images

Enforce file-size, page-count, row-count, and processing-time limits.
Validate actual file content/signature; do not trust extension or
browser MIME alone.

### 7.3 Processing pipeline

1.  **Upload:** authenticate user, resolve restaurant from membership,
    validate size/type.
2.  **Private storage:** store file and calculate checksum.
3.  **Classify:** workbook, CSV, text PDF, scanned PDF, or image.
4.  **Extract:** parse workbook sheets/cells; extract PDF text/tables;
    OCR scanned pages.
5.  **Normalize:** standardize dates, units, column labels, and numeric
    formats while preserving originals.
6.  **Map:** suggest ingredient/location matches against the restaurant
    master.
7.  **Validate:** required fields, arithmetic, dates, units, duplicates,
    and transaction meaning.
8.  **Review:** display original source beside extracted rows,
    confidence indicators, and corrections.
9.  **Approve:** record reviewer, timestamp, corrections, and decision.
10. **Post:** for inventory imports only, post eligible transactions
    atomically and idempotently.
11. **Audit:** retain source, extraction version, normalized output,
    review log, and linked transaction IDs under retention policy.

### 7.4 Extraction and OCR rules

For each extracted field preserve: - Raw extracted value. - Normalized
value. - Source location (sheet/cell, PDF page/table/row, or image
coordinates where possible). - Confidence/validation status. - User
correction, if any.

Highlight low-confidence values. Never invent missing quantities, dates,
units, or ingredient identities.

### 7.5 Supported register types

-   Daily opening/closing stock registers.
-   Ingredient usage sheets.
-   Wastage sheets.
-   Stock-in sheets only when the source explicitly represents incoming
    movement.

Rules: - Closing stock is a snapshot, not stock-in. - Usage posts
consumption only if not already recorded. - Wastage is distinct from
consumption. - A mismatch creates a discrepancy for review. - Never
overwrite ledger balance with a closing figure.

### 7.6 Lifecycle

``` text
UPLOADED
   |
PROCESSING
   |
REVIEW_REQUIRED
   |
STAFF_VERIFIED
   |
POSTED
```

Alternative states: `PROCESSING_FAILED`, `REJECTED`,
`DUPLICATE_CANDIDATE`, `DISCREPANCY_REQUIRES_REVIEW`,
`ANALYSIS_COMPLETE`.

Use explicit state transitions, authorization, and retry rules. A
retried job must not post twice.

### 7.7 Document security

Store files privately; use short-lived signed URLs or authenticated
delivery; scope each document to its restaurant; do not execute macros;
treat formulas and external links as untrusted; apply retention/deletion
policy; and do not send sensitive files to external AI providers unless
that processing is explicitly enabled and accepted.

## 8. IoT monitoring

### 8.1 Prototype hardware

The described prototype uses an ESP32, load cell (including a 20 kg
prototype unit), HX711 amplifier, and Wi-Fi. Actual hardware
configuration, load limits, calibration, and installation must be
verified before deployment.

### 8.2 Telemetry lifecycle

1.  ESP32 samples the HX711.
2.  Firmware applies calibration and filtering.
3.  Device creates a message with device identity, sequence number,
    timestamp, and measurement.
4.  Device authenticates to the ingestion endpoint.
5.  Backend validates device status, credentials, payload, sequence, and
    assigned restaurant/location.
6.  Backend persists raw telemetry.
7.  Latest-reading projection updates.
8.  Rules evaluate thresholds and data quality.
9.  Application displays reading and alerts.
10. A separate validated workflow determines whether a business
    inventory event should be posted.

### 8.3 Readings are not automatically stock transactions

A weight decrease may represent consumption, removal, movement,
cleaning, drift, or noise. An increase may represent refill,
repositioning, or noise. Preserve raw telemetry and require
state/evidence rules before deriving a business event.

### 8.4 Device reliability

-   Unique device identity and revocable credentials.
-   Device-to-restaurant/location assignment.
-   Calibration metadata/history.
-   Sequence numbers and replay protection.
-   Idempotent ingestion.
-   Last-seen/freshness monitoring.
-   Stable-reading windows and filtering.
-   Handling for stale, duplicated, out-of-order, or implausible
    readings.
-   Buffering during network loss where hardware supports it.
-   Device replacement/reassignment.
-   Alerts for offline status, drift, and abnormal readings.

### 8.5 Refill state machine

Suggested states:

``` text
CREATED
  -> WAITING_FOR_BASELINE
  -> REFILL_IN_PROGRESS
  -> WAITING_FOR_STABLE_READING
  -> COMPLETED
```

Also support `CANCELLED`, `EXPIRED`, `FAILED`, and
`REQUIRES_MANUAL_REVIEW`.

The baseline must be fresh and belong to the current session. Completion
must use a stable post-refill reading after the session began. Validate
transitions on the server, use collision-resistant IDs, and make state
updates atomic.

## 9. Barcode workflows

A barcode may identify an ingredient, batch, container, or storage
position according to the configured barcode scheme.

### Barcode stock-in

Scan → resolve ingredient → select destination → enter/confirm quantity,
unit, batch, expiry, and cost where applicable → confirm → backend
validates and posts.

### Barcode refill

Scan container → resolve ingredient/destination → confirm source
location and refill quantity/evidence → validate available stock → post
internal transfer → update both locations atomically.

A scan is not authorization. Unknown/ambiguous codes must lead to a safe
lookup or manual selection rather than a guess.

## 10. AI and analytics

### AI responsibilities

-   Document classification and extraction.
-   Ingredient/unit matching suggestions.
-   Natural-language inventory summaries.
-   Anomaly explanation.
-   Usage and wastage trend analysis.
-   Demand forecasting.
-   Advisory replenishment recommendations.
-   Cross-restaurant comparisons for authorized owners.

### Forecasting

Use clean time-indexed history. Consider historical consumption,
weekday/seasonality where supported, restaurant operating days,
stockouts, promotions/events when available, lead time, forecast
horizon, and uncertainty.

Store model version, training period, forecast horizon, evaluation
metrics, and output timestamp. A forecast is not a guarantee.

### Advisory recommendations

The product does not include procurement or purchase-order management.
It may still suggest that an ingredient is likely to run low. Consider
available stock, pending internal transfers, forecast demand during lead
time, safety stock, expiry risk, and uncertainty. Label recommendations
advisory.

### Data provenance

Clearly distinguish: - Posted transactions. - Raw sensor measurements. -
Unapproved OCR extraction. - User-entered observations. - Estimated
values. - Model predictions.

Do not blend these into one unlabeled number.

## 11. Independent POS

The POS is a separate sales/revenue domain. Potential scope:

-   Menu/catalog.
-   Orders and order items.
-   Bills and receipts.
-   Discounts and taxes.
-   Payment records.
-   Cancellations and refunds.
-   Sales history.
-   Daily closing.
-   Sales/revenue reports.

**POS orders must not automatically deduct inventory, call inventory
APIs, or create ingredient consumption transactions.** Owner analytics
may display POS and inventory metrics together by restaurant and period,
but their underlying transactions remain separate.

Use precise financial terms: gross sales, discounts, refunds, net sales,
taxes, and payment collections. Do not call net sales minus inventory
purchases profit. Profit requires a defined accounting model and
additional expense data.

## 12. Multi-tenant architecture

Suggested hierarchy:

``` text
Owner / Business Account
       |
       +-- Restaurant A
       |      +-- Manager
       |      +-- Staff
       |      +-- Inventory / IoT / Documents / POS
       |
       +-- Restaurant B
              +-- Manager
              +-- Staff
              +-- Inventory / Documents / POS
```

Rules:

-   Resolve restaurant access from authenticated membership.
-   Verify each resource belongs to the resolved restaurant.
-   Never trust a browser-supplied `restaurant_id`.
-   Owner consolidated access is limited to restaurants they own/manage.
-   Managers and staff are limited to assigned restaurants.
-   Enforce scope in backend services and use database row-level
    security (RLS) as defense in depth where correctly configured.
-   Test cross-tenant access for records, files, exports, devices, and
    reports.

Owner may select authorized restaurants and a consolidated view.
Manager/staff do not receive a cross-restaurant selector in the initial
model.

## 13. Recommended technology architecture

This is a target recommendation; inspect the current repository and
deployment before treating it as implemented.

### Frontend

-   React 18
-   TypeScript
-   Vite
-   Tailwind CSS
-   React Router
-   Accessible reusable components
-   Recharts or another maintained charting library
-   PWA service worker/installability
-   Camera and barcode integration where browser/device support permits

### Backend

-   Python and Flask REST API
-   Domain/service layer separate from route handlers
-   Request/response schema validation
-   Authentication and action-based authorization
-   Background jobs for OCR, document processing, and ML tasks
-   Structured logging and consistent error handling

### Data and infrastructure

-   PostgreSQL as recommended production relational database.
-   Versioned database migrations.
-   Private object storage for uploads and exports.
-   Background queue/worker for long-running tasks.
-   Redis only where justified for queueing, caching, or coordination.
-   Secret manager/environment-based secrets.
-   Monitoring, backups, and tested restore procedures.

### ML and document processing

-   Select OCR/PDF extraction tools using a representative
    restaurant-document test corpus.
-   Use a safe spreadsheet parser with resource limits.
-   Version forecasting models and evaluation runs.
-   Store model provenance and timestamps.
-   Abstract AI provider integrations behind a service boundary.

### Architecture flow

``` text
Web Browser / Mobile PWA
          |
          v
       Flask API
          |
          +-- Authentication / Authorization
          +-- Restaurant / Membership
          +-- Inventory Domain Services
          |       +-- Inventory Ledger
          |       +-- Balance Projections
          |       +-- Reconciliation
          +-- Document Intelligence
          |       +-- Private File Storage
          |       +-- OCR / Table Extraction
          |       +-- AI Mapping Suggestions
          |       +-- Review / Approval
          +-- IoT Device / Telemetry Services
          +-- POS Services (separate domain)
          +-- Analytics / Forecasting
                    |
                    v
                PostgreSQL

ESP32 / HX711 -- authenticated telemetry --> IoT ingestion
```

Start with a **modular monolith**: one deployable backend with clear
domain boundaries. Microservices add operational complexity and should
be introduced only when scale, team ownership, or independent deployment
needs justify them.

## 14. Conceptual data model

This is a conceptual model, not a migration script. Inspect and reuse
existing tables where semantics match.

### Identity and tenancy

-   `users`
-   `businesses` or `owner_accounts`
-   `restaurants`
-   `restaurant_memberships`
-   `roles`
-   `permissions`
-   `role_permissions`
-   `invitations`
-   `sessions` or token revocation records

### Ingredient and storage master data

-   `categories`
-   `ingredients` (or existing `products` if semantically suitable)
-   `units`
-   `unit_conversions`
-   `storage_locations`
-   `ingredient_location_configs`
-   `barcodes`

### Inventory

-   `inventory_balances` (projection/cache, not source of truth)
-   `inventory_transactions`
-   `inventory_transaction_lines`
-   `inventory_batches`
-   `stock_counts`
-   `stock_count_items`
-   `stock_in_records`
-   `transfers`
-   `wastage_records`
-   `adjustment_requests`
-   `inventory_idempotency_keys`

### IoT

-   `iot_devices`
-   `iot_device_assignments`
-   `iot_calibrations`
-   `iot_readings`
-   `iot_events`
-   `refill_sessions`
-   `iot_alerts`

### Documents

-   `document_uploads`
-   `document_extractions`
-   `document_extraction_items`
-   `document_review_logs`
-   `document_transaction_links`
-   `document_processing_jobs`

### AI and analytics

-   `ai_predictions`
-   `forecast_runs`
-   `forecast_metrics`
-   `anomaly_events`
-   `reorder_recommendations`
-   `analytics_snapshots`

### Independent POS

-   `menus`
-   `menu_items`
-   `pos_orders`
-   `pos_order_items`
-   `pos_bills`
-   `pos_payments`
-   `pos_refunds`
-   `pos_daily_closings`

### Audit and operations

-   `audit_logs`
-   `notifications`
-   `background_jobs`
-   `outbox_events`

Use foreign keys, constraints, tenant-scope indexes, UTC timestamps,
migrations, and collision-resistant identifiers. Do not erase posted
ledger history.

## 15. API design

Illustrative endpoint families; align names and conventions with the
existing codebase:

``` text
/api/v1/auth/*
/api/v1/me
/api/v1/restaurants
/api/v1/restaurants/{restaurant_id}/members
/api/v1/ingredients
/api/v1/storage-locations
/api/v1/inventory/balances
/api/v1/inventory/transactions
/api/v1/inventory/stock-in
/api/v1/inventory/transfers
/api/v1/inventory/stock-counts
/api/v1/inventory/wastage
/api/v1/barcodes/resolve
/api/v1/iot/devices
/api/v1/iot/telemetry
/api/v1/iot/refill-sessions
/api/v1/documents
/api/v1/documents/{document_id}/extraction
/api/v1/documents/{document_id}/review
/api/v1/documents/{document_id}/approve
/api/v1/documents/{document_id}/post
/api/v1/analytics/*
/api/v1/forecasts/*
/api/v1/pos/*
/api/v1/reports/*
```

API requirements: - Validate every request using explicit schemas. -
Return consistent errors and correct HTTP status codes. - Separate user
authentication from device authentication. - Enforce permissions and
tenant scope in backend services. - Paginate large results and bound
date ranges. - Use idempotency keys for retryable writes. - Use
concurrency/version checks where necessary. - Do not expose stack
traces. - Never put access tokens in query strings or URLs. - Authorize
exports and use short-lived access mechanisms.

## 16. Security

### Authentication

-   Secure password hashing (Argon2id or a suitably configured modern
    alternative).
-   Short-lived access tokens and secure session/refresh strategy.
-   Prefer secure HttpOnly SameSite cookies where the architecture
    permits.
-   Revoke sessions after logout, password reset, membership removal, or
    account disablement.
-   Rate-limit login and sensitive endpoints.
-   Never ship production demo credentials or public demo-login
    shortcuts.

### Authorization and tenant isolation

-   Backend-enforced action permissions.
-   Restaurant membership checks on every restaurant-owned operation.
-   File download, export, IoT, and report access must use the same
    scope controls.
-   Prevent horizontal privilege escalation and insecure direct object
    references.
-   Use correctly configured database RLS as defense in depth.

### Application and infrastructure

-   No hardcoded production secrets or insecure fallback secrets.
-   Restrict CORS to known origins.
-   HTTPS in deployed environments.
-   CSRF protection when cookie authentication is used.
-   Validate file signatures, size, and content.
-   Protect against SQL injection, XSS, path traversal, and unsafe
    parsing.
-   Patch dependencies and scan regularly.
-   Back up database and test restoration.
-   Keep tokens, passwords, and sensitive document contents out of logs.

### IoT

-   Unique revocable device credentials.
-   Credential rotation.
-   Authenticated ingestion.
-   Replay/duplicate protection.
-   Device assignment validation.

## 17. Mobile PWA and offline behavior

The first mobile experience should be an installable PWA; a dedicated
native Android app can be considered later if browser limitations
require it.

Mobile priorities: - Camera-based document capture. - Barcode scanning
where supported. - Large touch targets and short workflows. - Clear
network/sync status. - Responsive phone and tablet layouts.

Offline drafts may include stock counts, document captures, and wastage
reports. Do not claim an offline action has been posted.

On reconnection: 1. Revalidate the session. 2. Re-check restaurant
membership and permissions. 3. Revalidate current stock and business
rules. 4. Detect duplicates and conflicts. 5. Submit using idempotency
keys. 6. Show posted, rejected, conflict, or manual-review status.

Never silently replay stale inventory changes without revalidation.

## 18. Reliability and observability

Reliability requirements: - Database transactions for multi-record
inventory operations. - Idempotent request processing. - Durable
background job state and safe retries. - Dead-letter handling for
repeated job failures. - Ledger-to-projection reconciliation. - Backups
and tested restoration. - Explicit handling of database/object-storage
partial failures. - Graceful degradation when AI or IoT is unavailable.

Observe: - Structured application logs and correlation IDs. - API
latency/error rates. - Background job status/duration. - IoT last-seen
and ingestion failures. - Document processing failures. - Database
health and slow queries. - Inventory reconciliation failures.

Never log credentials, tokens, or sensitive document contents.

Potential alerts: sensor offline, stale reading, overdue calibration,
failed document job, repeated duplicate import, balance mismatch,
high-severity discrepancy, and queue backlog.

## 19. Testing and acceptance criteria

A successful frontend build is not evidence of inventory correctness.

### Unit tests

-   Quantity and unit conversions.
-   Balance calculations.
-   Transaction semantics.
-   Refill state transitions.
-   Permission evaluation.
-   Document validation.
-   Forecast input preparation.
-   POS calculations.

### Integration tests

-   Authentication and membership.
-   Restaurant-scoped reads/writes.
-   Stock-in.
-   Atomic internal transfers.
-   Stock count and adjustment.
-   Idempotency and retries.
-   IoT authentication and persistence.
-   Document extraction/review lifecycle.
-   Report export authorization.
-   POS isolation from inventory.

### End-to-end scenarios

**A. Two-restaurant isolation** 1. Owner creates Restaurant A and B. 2.
Owner assigns separate managers/staff. 3. Manager A attempts to access
B. 4. Backend rejects the request. 5. Owner can access both in an
authorized consolidated view.

**B. IoT restaurant** 1. Staff logs into Restaurant A. 2. IoT
capabilities appear according to configuration and permissions. 3.
Device sends authenticated telemetry. 4. Staff scans a container and
performs refill. 5. Source/destination balances update atomically. 6.
Consolidated restaurant stock does not increase due to internal refill.

**C. Traditional restaurant** 1. Staff logs into Restaurant B. 2. Staff
uploads stock register PDF or Excel. 3. System extracts rows and shows
source evidence. 4. Staff corrects uncertain values. 5. Backend detects
duplicates/discrepancies. 6. Eligible approved records are posted once.

**D. Analysis-only upload** 1. User uploads a historical spreadsheet. 2.
AI produces a report. 3. No inventory transaction is created.

**E. POS separation** 1. Staff completes a POS order. 2. POS
sales/payment records update. 3. Inventory balance and inventory ledger
remain unchanged.

### Release acceptance

-   Cross-tenant access tests pass.
-   Ledger and projection reconciliation passes.
-   Duplicate/retry tests pass.
-   Critical inventory operations are atomic.
-   File failures are recoverable.
-   POS separation is verified.
-   Device authentication and stale-reading behavior are tested.
-   Production secrets and CORS are configured safely.
-   Backup and restore have been tested.
-   Known limitations are documented.

## 20. Implementation roadmap

Build in dependency order. Do not ask an AI coding agent to implement
the entire platform in one unreviewed rewrite.

### Phase 0 --- Repository/domain audit

Inspect frontend, backend, schema, tests, and deployment. Separate
implemented behavior from mock UI. Map existing tables, identify
defects, and prepare a migration plan.

**Exit:** verified baseline, architecture decisions, prioritized
defects, migration plan.

### Phase 1 --- Foundation and tenancy

PostgreSQL schema/migrations, authentication,
business/restaurant/membership model, roles, permissions, tenant
isolation, and audit infrastructure.

**Exit:** owner/manager/staff access works; cross-tenant tests pass.

### Phase 2 --- Inventory ledger

Ingredient/storage master, stock-in, transfers/refills, counts,
consumption, wastage, adjustments, reconciliation, idempotency, and
concurrency.

**Exit:** balances reconcile from ledger events under retries and
concurrent operations.

### Phase 3 --- Staff PWA

Shared login, capability-aware navigation, IoT and traditional staff
dashboards, camera/barcode flows, offline drafts, and sync conflict
handling.

**Exit:** both restaurant types complete their staff workflows on real
mobile devices.

### Phase 4 --- Document intelligence

Excel/CSV parsing, PDF text/table extraction, scanned PDF OCR, review
UI, analysis-only reporting, controlled inventory import, duplicate
detection, and audit.

**Exit:** representative files can be extracted, reviewed, validated,
and posted without duplicate or silent stock changes.

### Phase 5 --- IoT integration

Device identity, telemetry ingestion, calibration/stable-reading logic,
device health, alerts, and refill state machine.

**Exit:** real hardware tests cover normal use, stale readings, network
loss, duplicate messages, and invalid credentials.

### Phase 6 --- AI and analytics

Data quality, forecast baseline/evaluation, anomaly detection,
wastage/usage analysis, advisory recommendations, and owner consolidated
reporting.

**Exit:** outputs include provenance, evaluation, uncertainty, and clear
actual-versus-prediction labels.

### Phase 7 --- Independent POS

Menu, orders, bills, payments, refunds, daily close, revenue reports,
and permissions.

**Exit:** POS works independently; tests prove it does not deduct
inventory.

### Phase 8 --- Production hardening

Security, load/concurrency, backup/restore, monitoring, deployment
automation, and restaurant user acceptance testing.

**Exit:** operational runbooks, tested recovery, security review, and
documented limitations.

## 21. Suggested repository structure

Adapt to the current repository rather than forcing a disruptive
rewrite.

``` text
smartstock-ai/
├── frontend/
│   └── src/
│       ├── app/
│       ├── routes/
│       ├── components/
│       ├── features/
│       │   ├── auth/
│       │   ├── owner/
│       │   ├── manager/
│       │   ├── staff/
│       │   ├── restaurants/
│       │   ├── inventory/
│       │   ├── barcode/
│       │   ├── documents/
│       │   ├── iot/
│       │   ├── analytics/
│       │   ├── forecasts/
│       │   ├── pos/
│       │   └── reports/
│       ├── services/
│       ├── hooks/
│       └── types/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── domain/
│   │   │   ├── inventory/
│   │   │   ├── restaurants/
│   │   │   ├── documents/
│   │   │   ├── iot/
│   │   │   ├── analytics/
│   │   │   └── pos/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── tasks/
│   │   ├── security/
│   │   └── config/
│   ├── migrations/
│   └── tests/
├── ml/
│   ├── forecasting/
│   ├── anomaly_detection/
│   └── evaluation/
├── iot/
│   ├── esp32/
│   ├── firmware/
│   └── calibration/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── workflows/
│   └── decisions/
├── .env.example
├── .gitignore
└── README.md
```

## 22. Local development

The repository's actual scripts and entry points must be checked before
relying on these example commands.

### Prerequisites

-   Git.
-   Node.js LTS and npm.
-   Python version supported by backend dependencies.
-   PostgreSQL for the recommended multi-tenant target.
-   Optional Redis/queue backend if background jobs require it.
-   ESP32 hardware for physical IoT testing.

### Clone

``` bash
git clone https://github.com/Veera03122005/smart-inventory-management-System.git
cd smart-inventory-management-System
```

### Backend environment

``` bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Configure the environment using the actual keys supported by the
backend, run migrations, and start Flask using the repository's
configured entry point.

### Frontend

``` bash
cd frontend
npm install
npm run dev
```

Run the configured backend tests, frontend type-check, lint (if
configured), and production build. Add integration and end-to-end tests
for critical workflows before declaring features complete.

## 23. Configuration

Maintain `.env.example` with variable names and safe placeholders only.
Never commit real credentials.

Illustrative configuration categories (align names to actual code):

``` dotenv
APP_ENV=development
SECRET_KEY=
FRONTEND_ORIGIN=

DATABASE_URL=

ACCESS_TOKEN_SECRET=
ACCESS_TOKEN_TTL=

OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_BUCKET=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=

REDIS_URL=

AI_PROVIDER=
AI_API_KEY=
OCR_PROVIDER=

IOT_INGESTION_SECRET=
IOT_ALLOWED_CLOCK_SKEW_SECONDS=
```

Production must fail closed when required secrets are missing. Do not
use known default secrets.

## 24. Deployment

A production deployment typically includes: - Frontend static
hosting/CDN. - Flask API hosting. - Managed PostgreSQL. - Private object
storage. - Background worker and queue. - Secret manager. - HTTPS and
domain configuration. - Monitoring and centralized logs. - Automated
database backups.

Use staged environments. Deploy schema changes through reviewed
migrations. Do not run destructive production migrations without a
backup, rollback plan, and tested procedure.

## 25. Explicit exclusions

The following are outside the current product scope:

-   Purchase-order management.
-   Procurement approvals.
-   Supplier invoice management.
-   Supplier payment tracking.
-   Accounts payable.
-   Procurement analytics.
-   Automatic POS-to-inventory deduction.
-   AI silently overwriting inventory balances.
-   Automatic posting of unverified OCR/spreadsheet output.

**Stock-in remains in scope.** It records incoming stock in inventory;
it is not a purchase-order/procurement workflow. Optional
supplier/source text may be retained as reference metadata, but it must
not become a procurement module without a separate product decision.

## 26. Definition of done

A feature is complete only when relevant layers are implemented and
tested:

1.  Workflow and acceptance criteria defined.
2.  UI handles loading, empty, success, error, and permission states.
3.  API validates input and returns consistent responses.
4.  Backend enforces permission and restaurant scope.
5.  Database constraints and migrations exist.
6.  Business rules are implemented in domain/service code.
7.  Audit and idempotency behavior are defined.
8.  Unit and integration tests pass.
9.  End-to-end tests cover the real workflow.
10. Failure, retry, and concurrency cases are addressed.
11. Documentation reflects actual behavior.
12. Deployment configuration is secure.

A mock dashboard, successful TypeScript compilation, or a small
happy-path test suite is not sufficient evidence of production
readiness.

## 27. Implementation status

This README describes the target product. It does not certify the
current repository's implementation status.

Maintain a verified matrix and update it only with reproducible
evidence:

  -----------------------------------------------------------------------
  Capability              Initial status          Evidence required
  ----------------------- ----------------------- -----------------------
  Authentication          To verify               Backend tests and
                                                  session review

  Owner/manager/staff     To verify               Permission and
  permissions                                     negative-access tests

  Multi-restaurant        To verify               Cross-tenant
  isolation                                       integration tests

  Inventory ledger        To verify               Reconciliation and
                                                  concurrency tests

  Stock-in and refill     To verify               End-to-end transaction
                                                  tests

  IoT telemetry           To verify               Actual ESP32
                                                  integration tests

  Barcode workflows       To verify               Device/browser tests

  Excel/PDF upload        To verify               Representative file
                                                  test corpus

  OCR and document review To verify               Extraction accuracy and
                                                  review tests

  AI                      To verify               Model evaluation and
  analytics/forecasting                           provenance

  Independent POS         To verify               Tests proving no
                                                  inventory coupling

  PWA/offline drafts      To verify               Real mobile and
                                                  reconnect tests

  Production security     To verify               Security review and
                                                  deployment checks
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Engineering principle

**Build SmartStock AI around a reliable inventory domain---not around
dashboards or AI features.**

The recommended sequence is:

1.  Establish identity and tenant isolation.
2.  Establish inventory ledger and transaction semantics.
3.  Build reliable operational workflows.
4.  Add document and IoT capture channels.
5.  Add AI analysis and forecasting on validated data.
6.  Add independent POS and combined owner analytics.
7.  Harden, test, monitor, and deploy.

This order reduces rework and prevents attractive interfaces from hiding
incorrect stock calculations or insecure access controls.

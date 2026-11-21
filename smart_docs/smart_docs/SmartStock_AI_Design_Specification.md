# SmartStock AI --- System Design & Implementation Specification

**Document type:** Software, IoT, ML and deployment design\
**Version:** 1.0\
**Date:** 18 November 2026\
**Status:** Development baseline --- validate against the live
repository and Supabase schema before implementation

------------------------------------------------------------------------

## 1. Purpose

SmartStock AI is a hybrid restaurant ingredient-inventory system. It
combines:

1.  Load-cell telemetry from an ESP32 + HX711 weighing unit.
2.  Barcode-initiated refill sessions that distinguish stock additions
    from depletion.
3.  Manual stock-register entries for ingredients without sensors.
4.  Daily ingredient-depletion reconstruction and demand forecasting.
5.  Forecast-driven replenishment with batch, FIFO and expiry tracking.
6.  A role-aware web dashboard for staff, managers and owners.

The design is based on the uploaded six-page IEEE paper, *SmartStock AI:
A Hybrid IoT and Machine Learning Framework for Ingredient Demand
Forecasting and Replenishment in Restaurants*. The paper's reported
model and replenishment metrics are simulation results, not validated
live-restaurant results.

## 2. Goals and non-goals

### 2.1 Goals

-   Maintain a single auditable inventory ledger for sensor and manual
    activity.
-   Prevent validated refills from being recorded as ingredient
    depletion.
-   Record batch number, received quantity and expiry date at stock-in.
-   Support sensor and non-sensor ingredients.
-   Produce reproducible daily depletion series.
-   Forecast ingredient demand and compare models against simple
    baselines.
-   Calculate reorder point, order-up-to level and recommended order
    quantity.
-   Enforce tenant, role and device access boundaries.
-   Provide operational visibility into sensor health, stock, expiry,
    forecasts and recommendations.

### 2.2 Non-goals for the first release

-   Automatic POS integration.
-   Fully autonomous purchasing or supplier payment.
-   Computer vision for ingredient recognition.
-   Guaranteed identification of cooking consumption versus wastage from
    weight alone.
-   Claims of production-grade forecast accuracy before real-world
    validation.

## 3. Evidence and design decisions

### 3.1 Requirements taken from the paper

-   Hardware: 20 kg single-point load cell, HX711 24-bit ADC and ESP32.
-   Stable reading: standard deviation of the last ten samples below 5
    g.
-   Sensor message: device identifier, sequence number, timestamp,
    weight and stability flag, sent as HTTPS JSON.
-   Backend: Flask REST API.
-   Data store: Supabase PostgreSQL.
-   Authentication: Supabase Auth, role-based access and row-level
    security.
-   Manual channel: received stock, issued quantity, wastage and closing
    stock.
-   Refill: barcode scan, stable pre-refill reading,
    batch/quantity/expiry capture, stable post-refill reading and
    validated weight delta.
-   Forecast candidates: Random Forest and XGBoost.
-   Baselines: seasonal naive (previous seven-day value) and seven-day
    moving average.
-   Forecast features: lags 1, 2, 7 and 14; rolling means 7 and 28;
    rolling standard deviation 7; weekday profile;
    weekday/weekend/month/Purattasi/festival features.
-   Replenishment: reorder point, order-up-to level, safety stock, FIFO
    and expiry handling.
-   Paper evaluation: six simulated ingredients, 488 days, five random
    seeds, 427 training days and 61 test days.

### 3.2 Decisions requiring confirmation

The paper does not fully specify the following. These must be decided,
documented and tested rather than silently assumed:

-   Whether one forecasting model is trained per ingredient or a global
    model is used.
-   Refill threshold, session timeout and stable-reading duration.
-   Exact weekday-profile estimation and fallback for manual
    reconstruction.
-   Device authentication and key rotation.
-   Tenant model and restaurant onboarding process.
-   Sensor calibration procedure, drift checks and allowable error.
-   Exact order quantities, minimum order quantities, supplier
    constraints and procurement costs.
-   Whether stock depletion is treated as demand or split into cooking
    use, wastage and other adjustments.
-   Retention periods, backup policy and operational service-level
    objectives.

## 4. Users, roles and permissions

  --------------------------------------------------------------------------
  Role              Read              Create/update     Approve/administer
  ----------------- ----------------- ----------------- --------------------
  Staff             Assigned          Manual entries,   No
                    inventory,        refill sessions,  
                    batches, alerts   wastage records   

  Manager           Restaurant        Inventory         Approve
                    inventory,        corrections,      adjustments/orders
                    forecasts,        purchase orders   
                    reports                             

  Owner/Admin       All restaurant    Configuration,    Roles, policies,
                    data and users    devices,          device lifecycle
                                      suppliers         

  IoT device        Its own device    Telemetry only    No human-user
                    registration and                    privileges
                    assigned                            
                    inventory                           
                    endpoint                            
  --------------------------------------------------------------------------

Authorization must be enforced server-side and in PostgreSQL RLS
policies. Hiding a UI control is not authorization.

## 5. High-level architecture

``` mermaid
flowchart LR
    LC[Load cell] --> HX[HX711]
    HX --> ESP[ESP32 firmware]
    ESP -->|HTTPS JSON| API[Flask REST API]
    SCAN[Barcode scanner / mobile camera] --> WEB[React web app]
    MANUAL[Manual stock register] --> WEB
    WEB -->|Authenticated API| API
    API --> DB[(Supabase PostgreSQL)]
    DB --> JOB[Scheduled aggregation / ML job]
    JOB --> FE[Forecasting models]
    FE --> POLICY[Replenishment policy]
    POLICY --> DB
    DB --> WEB
```

### 5.1 Component responsibilities

**React + TypeScript + Vite** - Responsive staff and manager
interface. - Forms, barcode capture, tables, charts and status
indicators. - Calls authenticated Flask endpoints. - Never contains
service-role keys or device secrets.

**Flask REST API** - Validates users, devices, payloads and business
rules. - Enforces idempotency and transaction boundaries. - Writes
inventory ledger events. - Exposes reporting and operational APIs. -
Does not trust client-calculated stock balances.

**Supabase PostgreSQL** - Source of truth for inventory, transactions,
batches, telemetry and forecasts. - RLS protects user-facing access. -
Database constraints protect referential integrity and uniqueness.

**ML worker** - Builds point-in-time-safe training data. - Trains and
evaluates forecasting models. - Writes versioned predictions and
evaluation metrics. - Runs separately from latency-sensitive request
handling.

**ESP32** - Reads HX711 samples. - Performs tare/calibration and
stability checks. - Sends signed/authenticated telemetry with sequence
numbers. - Buffers a bounded amount of telemetry during connectivity
loss if implemented.

## 6. Data model

The following is a logical schema. Reconcile it with the existing
Supabase database before creating migrations.

### 6.1 Core entities

  --------------------------------------------------------------------------
  Table                     Important fields         Purpose
  ------------------------- ------------------------ -----------------------
  restaurants               id, name, timezone,      Tenant boundary
                            created_at               

  users / memberships       user_id, restaurant_id,  Restaurant membership
                            role, active             and role

  categories                id, restaurant_id, name  Ingredient grouping

  products                  id, restaurant_id,       Ingredient catalogue
                            category_id, name, unit, 
                            shelf_life_days,         
                            lead_time_days, active   

  product_barcodes          id, restaurant_id,       Barcode-to-ingredient
                            product_id, barcode,     mapping
                            active                   

  storage_units             id, restaurant_id, name, Physical storage
                            location, tare_weight    

  inventory                 id, restaurant_id,       Current stock
                            product_id,              projection
                            storage_unit_id,         
                            current_quantity,        
                            updated_at               

  inventory_transactions    id, restaurant_id,       Immutable stock ledger
                            inventory_id, type,      
                            quantity, unit, source,  
                            occurred_at,             
                            idempotency_key,         
                            actor_id, metadata       

  inventory_batches         id, restaurant_id,       Batch and expiry
                            inventory_id,            tracking
                            batch_number,            
                            received_quantity,       
                            remaining_quantity,      
                            received_at,             
                            expiry_date, supplier_id 

  iot_devices               id, restaurant_id,       Device registration
                            device_code,             
                            inventory_id, status,    
                            last_seen_at,            
                            credential_hash          

  iot_readings              id, device_id,           Raw telemetry
                            sequence_number,         
                            measured_at, weight,     
                            stable, received_at,     
                            raw_payload              

  refill_sessions           id, restaurant_id,       Refill workflow audit
                            inventory_id, barcode,   
                            before_weight,           
                            after_weight, delta,     
                            batch_id, status,        
                            started_at,              
                            completed_at, actor_id   

  manual_stock_entries      id, restaurant_id,       Manual register
                            inventory_id,            
                            entry_date,              
                            opening_stock, received, 
                            issued, wastage,         
                            closing_stock,           
                            entered_by               

  daily_depletion           id, restaurant_id,       Forecast target series
                            inventory_id, date,      
                            quantity, source,        
                            reconstruction_version   

  model_runs                id, restaurant_id,       Model reproducibility
                            model_name,              
                            model_version,           
                            training_cutoff,         
                            feature_version,         
                            metrics, created_at      

  ai_predictions            id, restaurant_id,       Forecast output
                            inventory_id,            
                            target_date, horizon,    
                            predicted_quantity,      
                            model_run_id, created_at 

  reorder_recommendations   id, restaurant_id,       Purchase recommendation
                            inventory_id, as_of,     
                            reorder_point,           
                            order_up_to,             
                            recommended_quantity,    
                            rationale, status        

  suppliers                 id, restaurant_id, name, Supplier catalogue
                            contact_details          

  alerts                    id, restaurant_id,       Operational alerts
                            inventory_id, type,      
                            severity, message,       
                            status, created_at       

  audit_logs                id, restaurant_id,       Administrative audit
                            actor_type, actor_id,    trail
                            action, entity_type,     
                            entity_id, before_state, 
                            after_state, created_at  
  --------------------------------------------------------------------------

### 6.2 Database invariants

-   Every restaurant-owned row carries `restaurant_id`.
-   Foreign keys must prevent cross-restaurant references.
-   Barcode uniqueness should be scoped appropriately, normally by
    restaurant.
-   `(device_id, sequence_number)` must be unique.
-   Idempotency keys must prevent duplicate stock transactions.
-   Quantities must be non-negative unless a documented adjustment type
    permits otherwise.
-   Store timestamps in UTC; render them using the restaurant timezone.
-   Preserve raw telemetry separately from derived inventory
    transactions.
-   Treat the transaction ledger as authoritative;
    `inventory.current_quantity` is a projection that can be reconciled.
-   Do not delete posted stock transactions; reverse them with
    compensating transactions.

## 7. Inventory accounting and transaction rules

### 7.1 Stock ledger

Represent stock movements using explicit transaction types:

-   `OPENING_BALANCE`
-   `RECEIPT`
-   `CONSUMPTION` or `DEPLETION`
-   `WASTAGE`
-   `ADJUSTMENT_IN`
-   `ADJUSTMENT_OUT`
-   `TRANSFER_IN`
-   `TRANSFER_OUT`
-   `EXPIRY`
-   `RETURN_TO_SUPPLIER`

Use signed quantities consistently or use a documented direction field.
Never mix conventions.

### 7.2 Sensor depletion

The paper's daily formula is:

\[ C_t = W\_{open,t} + R_t - W\_{close,t} \]

where (R_t) is the sum of validated refills for that day.

Before using this formula: - Convert all readings to the same mass
unit. - Correct for container tare consistently. - Require valid stable
readings at opening and closing. - Associate each refill with the
correct inventory position. - Exclude the refill window from ordinary
depletion inference. - Flag negative or implausible depletion for
review. - Define day boundaries using restaurant-local time.

A weight sensor alone measures stock movement; it cannot identify
whether removed ingredients were cooked, wasted or otherwise removed.
Record those distinctions through staff/POS events where available.

### 7.3 Barcode refill state machine

``` mermaid
stateDiagram-v2
    [*] --> AwaitBarcode
    AwaitBarcode --> ResolveBarcode
    ResolveBarcode --> CaptureBefore: unique active mapping
    ResolveBarcode --> Rejected: unknown / ambiguous barcode
    CaptureBefore --> AwaitStockAddition: stable reading
    CaptureBefore --> Rejected: timeout / unstable
    AwaitStockAddition --> CaptureAfter: staff confirms addition
    CaptureAfter --> ValidateDelta: stable reading
    ValidateDelta --> CommitRefill: delta passes validation
    ValidateDelta --> Rejected: invalid delta / timeout
    CommitRefill --> [*]
    Rejected --> [*]
```

Required validations: - Barcode resolves to exactly one active
product/storage mapping. - Device is assigned to the same inventory
position. - Before and after readings meet stability requirements. -
`delta = after_weight - before_weight` is positive and within configured
limits. - Entered received quantity and measured delta are compared;
mismatch creates a review flag. - Batch number and expiry date are
captured. - Refill transaction and batch creation occur atomically. -
Session has a unique idempotency key. - Rejected sessions remain
auditable.

## 8. IoT hardware and firmware requirements

### 8.1 Hardware bill of materials

  Item                        Specification / purpose
  --------------------------- --------------------------------------------------
  ESP32 development board     Wi-Fi microcontroller
  Single-point load cell      20 kg capacity as stated in paper
  HX711 module                Load-cell ADC/amplifier
  Stable platform             Mechanical load transfer
  Power supply                Regulated supply appropriate to board and module
  Enclosure and wiring        Protection and strain relief
  Calibration masses          Known reference masses
  Optional status indicator   Device state and fault indication

Confirm the exact ESP32 board, load-cell wiring, HX711 breakout and
power arrangement before finalising pin assignments.

### 8.2 Firmware behaviour

1.  Initialise hardware and verify sensor communication.
2.  Load calibration factor and tare configuration.
3.  Sample the load cell.
4.  Apply filtering and calculate stability over the last ten samples.
5.  Mark stable when the standard deviation is below the paper's 5 g
    threshold, after validating that threshold experimentally.
6.  Attach device ID, sequence number, timestamp, weight and stability
    flag.
7.  Transmit over authenticated HTTPS.
8.  Retry transient failures without reusing a new sequence number for
    the same reading.
9.  Expose health state, last successful send and sensor faults.
10. Never silently convert sensor failure into a zero-weight reading.

### 8.3 Calibration and hardware validation

Record: - Calibration date and operator. - Reference masses and test
points. - Error at each test point. - Repeatability across repeated
measurements. - Zero drift over time. - Hysteresis when loading and
unloading. - Response to vibration and container movement. - Packet
delivery rate and end-to-end latency. - Performance near the intended
operating temperature.

Do not claim sensor accuracy or reliability until these measurements
exist.

## 9. API design

Use versioned JSON endpoints. Exact schemas and authentication mechanics
must be finalised during implementation.

  ------------------------------------------------------------------------------------------------
  Method                  Endpoint                                         Purpose
  ----------------------- ------------------------------------------------ -----------------------
  GET                     `/api/v1/health`                                 Service health

  GET/POST                `/api/v1/products`                               List/create ingredients

  GET/PATCH               `/api/v1/products/{id}`                          Read/update ingredient

  GET                     `/api/v1/inventory`                              Inventory balances

  GET/POST                `/api/v1/inventory/{id}/transactions`            Read/post movements

  POST                    `/api/v1/refill-sessions`                        Start refill session

  POST                    `/api/v1/refill-sessions/{id}/complete`          Complete refill

  POST                    `/api/v1/refill-sessions/{id}/reject`            Reject refill

  POST                    `/api/v1/manual-entries`                         Submit manual register
                                                                           entry

  POST                    `/api/v1/iot/telemetry`                          Receive device
                                                                           telemetry

  GET                     `/api/v1/iot/devices`                            Device status

  GET                     `/api/v1/forecasts`                              Retrieve forecasts

  POST                    `/api/v1/forecasts/run`                          Trigger authorised
                                                                           forecast job

  GET                     `/api/v1/reorder-recommendations`                View order
                                                                           recommendations

  POST                    `/api/v1/reorder-recommendations/{id}/approve`   Approve recommendation

  GET                     `/api/v1/reports/consumption`                    Consumption report

  GET                     `/api/v1/reports/expiry`                         Expiry report
  ------------------------------------------------------------------------------------------------

### 9.1 API requirements

-   Validate request schema and units.
-   Enforce authentication and role permissions.
-   Use idempotency for telemetry and stock-changing requests.
-   Apply rate limits to public-facing and device endpoints.
-   Use parameterised SQL or safe ORM queries.
-   Return consistent error objects and appropriate HTTP status codes.
-   Avoid exposing stack traces, secrets or internal SQL details.
-   Log correlation IDs without logging credentials or sensitive
    payloads.
-   Use database transactions for multi-row stock operations.

## 10. Frontend information architecture

### 10.1 Main navigation

1.  Overview
2.  Inventory
3.  Ingredients
4.  Barcode Refill
5.  Manual Register
6.  IoT Devices
7.  Forecasting
8.  Replenishment
9.  Batches & Expiry
10. Reports
11. Users & Settings

### 10.2 Key screens

**Overview** - Total active ingredients. - Low-stock count. -
Expiring/expired batches. - Device online/offline status. - Daily
depletion chart. - Forecast versus actual chart. - Pending reorder
recommendations.

**Inventory** - Ingredient, category, storage location and unit. -
Current stock and days of cover. - Reorder point and status. - Data
source and last updated time. - Search, filters and transaction history.

**Ingredient detail** - Current stock. - Stock movement timeline. -
Batch list and expiry dates. - Sensor assignment. - Historical
consumption. - Forecast and recommendation.

**Refill** - Barcode input/camera scan. - Resolved ingredient and
storage unit. - Before weight. - Batch number, received quantity and
expiry. - After weight and measured delta. - Validation result and
confirmation.

**IoT devices** - Device identity and assigned inventory. -
Online/offline/unstable status. - Last telemetry time. - Latest
weight. - Sequence and delivery errors. - Calibration status.

**Forecasting** - Ingredient and date-range selection. - Actual versus
predicted values. - Model and version. - MAE, RMSE and WAPE. - Baseline
comparisons. - Data-quality warnings.

**Replenishment** - On-hand and on-order quantities. - Forecast over
lead time. - Reorder point and order-up-to level. - Recommended order
quantity. - Expiry and supplier context. - Approve/reject with reason.

## 11. Machine-learning design

### 11.1 Target definition

The paper's sensor equation estimates stock depletion. Unless cooking
usage can be separated from wastage and other removals, the model target
should be named `daily_depletion`, not assumed to be pure customer
demand.

### 11.2 Features

Use only information available at the forecast origin:

-   Lags: 1, 2, 7 and 14 days.
-   Rolling means: 7 and 28 days.
-   Rolling standard deviation: 7 days.
-   Same-weekday historical mean over four weeks.
-   Day of week, weekend and month.
-   Restaurant-relevant festival indicators.
-   Purattasi indicator where relevant to the restaurant's demand
    pattern.

All rolling calculations must be shifted so the target day's value
cannot leak into its own features.

### 11.3 Models

-   Seasonal naive: (`\hat `{=tex}y_t = y\_{t-7}).
-   Seven-day moving average.
-   Random Forest.
-   XGBoost.

The paper's reported configurations: - Random Forest: 300 trees, maximum
depth 10, minimum samples per leaf 2. - XGBoost: 400 boosting rounds,
learning rate 0.05, maximum depth 4, row and column subsampling 0.8.

Treat these as initial reproduction settings, not proven optimal
production settings.

### 11.4 Evaluation

Report: - MAE. - RMSE. - WAPE. - Per-ingredient metrics. - Aggregate
metrics. - Results by channel. - Results by seasonal period. - Ablation
results. - Confidence intervals or appropriate variability estimates.

Use chronological splits or rolling-origin evaluation. Do not randomly
shuffle time-series observations. Fit preprocessing and model parameters
only on training data.

### 11.5 Model lifecycle

Each model run must record: - Model name/version. - Training data
cutoff. - Feature version. - Training window. - Hyperparameters. -
Random seed. - Validation results. - Test results. - Code version. -
Creation timestamp.

Forecasts must be reproducible and traceable to a model run.

## 12. Replenishment and expiry logic

The paper specifies:

\[ s_t = `\sum`{=tex}*{k=1}\^{L}`\hat `{=tex}y*{t+k} +
z`\sigma`{=tex}\_e`\sqrt `{=tex}L \]

\[ S_t = `\sum`{=tex}*{k=1}\^{H}`\hat `{=tex}y*{t+k} +
z`\sigma`{=tex}\_e`\sqrt `{=tex}H \]

\[ Q_t = `\max`{=tex}(0,S_t-I_t-O_t) \]

Where: - (s_t): reorder point. - (S_t): order-up-to level. - (L):
supplier lead time. - (H): review/order-up-to horizon. - (z): safety
factor. - (`\sigma`{=tex}\_e): forecast residual standard deviation. -
(I_t): on-hand stock. - (O_t): on-order stock.

Paper settings: safety factor (z=2.05); perishable items reviewed daily
with (H=L); dry goods use a weekly ordering cycle with (H=L+7).

Implementation requirements: - Define whether on-hand stock excludes
expired or quarantined batches. - Avoid double-counting stock already on
order. - Use ingredient-specific lead times and forecast errors. -
Handle supplier minimum order quantities and pack sizes. - Apply FIFO
for issue allocation. - Flag batches before expiry using configurable
warning windows. - Prevent expired stock from being recommended for
use. - Record recommendation rationale and approval history.

The square-root safety-stock formula relies on assumptions about
forecast errors. Validate those assumptions, especially for multi-day
recursive forecasts.

## 13. Security and privacy requirements

-   Use Supabase Auth for human-user identity.
-   Enforce RLS on all tenant-owned tables.
-   Test cross-tenant read and write denial.
-   Never expose the Supabase service-role key in frontend code.
-   Use separate device credentials; do not reuse human-user access
    tokens for devices.
-   Store device secrets securely and support rotation/revocation.
-   Require HTTPS for network communication.
-   Validate and bound all user/device inputs.
-   Apply least-privilege database roles.
-   Audit privileged stock adjustments, approvals and user changes.
-   Back up the database and test restoration.
-   Keep secrets in environment variables or a managed secret store.
-   Define retention and deletion policies for operational data.

Security acceptance tests must verify actual enforcement, not merely the
presence of authentication libraries or RLS being enabled.

## 14. Testing strategy

### 14.1 Unit tests

-   Stock balance calculations.
-   Refill delta and threshold validation.
-   Manual reconstruction.
-   Feature generation and leakage checks.
-   Forecast metrics.
-   Reorder point and order quantity.
-   FIFO allocation and expiry handling.
-   Permission rules.

### 14.2 Integration tests

-   React → Flask authenticated API.
-   Flask → PostgreSQL transaction consistency.
-   ESP32 → telemetry endpoint.
-   Telemetry → inventory projection.
-   Refill session → batch and ledger creation.
-   Manual entry → daily depletion.
-   ML job → forecast persistence.
-   Forecast → replenishment recommendation.

### 14.3 Hardware tests

-   Calibration at multiple known weights.
-   Repeated load/unload measurements.
-   Empty-container tare stability.
-   Vibration and temperature effects.
-   Network disconnection and reconnection.
-   Duplicate and out-of-order telemetry.
-   Refill with and without barcode scan.
-   Sensor disconnection and recovery.

### 14.4 Security tests

-   Unauthenticated API access.
-   Staff attempting manager-only actions.
-   Cross-restaurant data access.
-   Forged device identity.
-   Replayed telemetry.
-   Duplicate transaction requests.
-   Invalid barcode and malformed payload.
-   SQL injection and input validation.
-   Secret exposure in frontend build.

## 15. Observability and operational requirements

Monitor: - API request latency and error rate. - Telemetry
acceptance/rejection rate. - Device last-seen time. - Duplicate sequence
count. - Sensor stability and calibration state. - Failed background
jobs. - Forecast job completion. - Data freshness. - Inventory
reconciliation differences.

Provide structured logs and alerts. Do not log passwords, tokens, device
secrets or unnecessary personal data.

## 16. Deployment design

Suggested environments:

-   Local development.
-   Staging/test restaurant.
-   Production.

Deployment checklist: - Separate environment variables and
credentials. - Database migrations under version control. - RLS policies
tested in staging. - HTTPS enabled. - CORS restricted to approved
frontend origins. - Background ML job scheduled independently. -
Database backup and restore procedure tested. - Health checks and error
monitoring configured. - Rollback procedure documented. - No sample/demo
data mixed with production inventory.

## 17. Development milestones and deliverables

  Milestone   Deliverable                     Completion evidence
  ----------- ------------------------------- ---------------------------------------------
  M1          Repository and database audit   Schema and API inventory
  M2          Secure backend foundation       Passing API/auth tests
  M3          Core React application          Working inventory screens
  M4          Stock ledger and manual entry   Reconciled transaction tests
  M5          Barcode refill workflow         Validated end-to-end refill
  M6          ESP32/HX711 integration         Calibration and telemetry report
  M7          Forecasting pipeline            Reproducible evaluation
  M8          Replenishment and expiry        Verified policy simulation
  M9          Security and integration        Test report and issue closure
  M10         Pilot deployment                Real restaurant data and operational report

Do not mark a milestone complete based only on UI appearance. Require
test evidence and reproducible results.

## 18. Acceptance criteria for the first complete demonstration

The first complete demonstration should show this sequence:

1.  Manager creates an ingredient and maps a barcode.
2.  Manager assigns the ingredient to a storage unit and IoT device.
3.  ESP32 sends a stable weight reading.
4.  Dashboard displays the latest reading and stock status.
5.  Staff scans the barcode to begin a refill.
6.  System captures before and after weights.
7.  Refill is recorded with batch number and expiry date.
8.  Inventory ledger reflects the receipt exactly once.
9.  Daily depletion calculation excludes the refill event.
10. Manual entries can be recorded for a non-sensor ingredient.
11. Forecasting job generates a future depletion forecast.
12. Replenishment engine produces an explainable recommendation.
13. Batch/expiry screen shows FIFO and expiry status.
14. A staff account is prevented from performing manager-only actions.

## 19. Research validation plan

The uploaded paper reports simulation-based results. The implementation
must create a separate real-world validation dataset.

Collect: - Reference weight and measured weight. - Calibration and
repeatability measurements. - Refill session outcomes. - Manual register
records. - Daily stock depletion. - Batch and expiry events. - Telemetry
packet delivery and latency. - Forecast predictions and actual
outcomes. - Purchase recommendations and resulting stockouts/spoilage.

For a pilot: - Record the restaurant and ingredient context. - Define a
data-collection protocol before starting. - Preserve raw data and
version derived datasets. - Compare forecasts against seasonal-naive and
moving-average baselines. - Report per-ingredient and aggregate
metrics. - Avoid presenting simulated results as field results. -
Document missing data and operational failures.

The paper itself proposes at least a three-month working-restaurant
pilot and future POS integration. Treat these as research objectives,
not completed capabilities.

## 20. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Weight changes misclassified as     Explicit refill sessions and manual
  consumption                         adjustment events

  Staff forget barcode scan           Reconciliation alerts and manual
                                      exception workflow

  Sensor drift                        Calibration schedule and drift
                                      monitoring

  Network outage                      Bounded local buffering and
                                      idempotent replay

  Incorrect manual reconstruction     Confidence flags and sensitivity
                                      evaluation

  Forecast leakage                    Chronological evaluation and
                                      automated leakage tests

  Expired stock counted as available  Batch-aware available-stock
                                      calculation

  Cross-tenant data exposure          RLS, API authorisation and
                                      adversarial tests

  Synthetic results overclaimed       Clearly separate simulation and
                                      field results

  Duplicate stock updates             Database uniqueness and idempotency
                                      constraints
  -----------------------------------------------------------------------

## 21. Official technical references

Use official documentation and primary technical sources during
implementation. Pin dependency versions and re-check documentation when
selecting versions.

1.  **Supabase Row Level Security:**
    https://supabase.com/docs/guides/database/postgres/row-level-security
2.  **Supabase Auth:** https://supabase.com/docs/guides/auth
3.  **Supabase Database:**
    https://supabase.com/docs/guides/database/overview
4.  **Flask documentation:** https://flask.palletsprojects.com/
5.  **Flask security considerations:**
    https://flask.palletsprojects.com/en/stable/web-security/
6.  **Espressif ESP-IDF documentation:**
    https://docs.espressif.com/projects/esp-idf/en/stable/esp32/
7.  **Espressif HTTPS client:**
    https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/protocols/esp_http_client.html
8.  **HX711 datasheet:**
    https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf
9.  **scikit-learn time-series cross-validation:**
    https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
10. **scikit-learn Random Forest regressor:**
    https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html
11. **XGBoost documentation:** https://xgboost.readthedocs.io/
12. **React documentation:** https://react.dev/
13. **Vite documentation:** https://vite.dev/guide/
14. **TypeScript documentation:** https://www.typescriptlang.org/docs/
15. **PostgreSQL constraints:**
    https://www.postgresql.org/docs/current/ddl-constraints.html
16. **OWASP API Security Top 10:**
    https://owasp.org/www-project-api-security/

These references are implementation starting points. The selected
library versions, exact hardware board and conference requirements must
be verified before release.

## 22. Final engineering principles

1.  The inventory ledger is the source of truth.
2.  Current stock is a derived, reconcilable projection.
3.  A refill is not consumption.
4.  A load cell measures weight movement, not the reason for removal.
5.  Manual reconstruction is an estimate and must be labelled as such.
6.  Forecasting must use only information available at prediction time.
7.  Every prediction must be traceable to its model and feature version.
8.  Purchase recommendations must be explainable.
9.  Security must be enforced at the database and API layers.
10. Simulation performance must never be represented as live deployment
    performance.

------------------------------------------------------------------------

**Implementation status:** This document defines the proposed target
design. It does not assert that the listed modules, database
relationships, security controls, tests or hardware behaviours are
already implemented. The existing repository and Supabase schema must be
audited before migrations or code changes are made.

## 23. Web-researched implementation clarifications (checked 18 November 2026)

The following points were checked against current official or primary
documentation and should be treated as implementation requirements:

### 23.1 Supabase authorization: RLS and grants are both required

Supabase's current RLS guidance states that row policies do not revoke
SQL privileges. Review table grants and RLS policies together for every
exposed table. Keep service-role/secret keys on trusted servers only
because they bypass RLS. Review views and `SECURITY DEFINER` functions
separately because they can create access paths that bypass the expected
row restrictions.

References: -
https://supabase.com/docs/guides/database/postgres/row-level-security -
https://supabase.com/docs/guides/api/securing-your-api -
https://supabase.com/docs/guides/security/production-checklist

### 23.2 ESP32 HTTPS must verify the server certificate

ESP-IDF's HTTP client supports HTTPS. For server verification, configure
a trusted root certificate using the certificate PEM setting or the ESP
x509 certificate bundle. Do not treat encryption without server
authentication as sufficient protection.

Reference: -
https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/protocols/esp_http_client.html

### 23.3 Time-series validation must preserve chronology

Scikit-learn documents `TimeSeriesSplit` for time-ordered data and
explains why ordinary shuffled cross-validation can train on future
observations and evaluate on earlier observations. Use chronological or
rolling-origin evaluation, ensuring all feature construction and
preprocessing are fitted using data available at each training cutoff.

References: -
https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html -
https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data

### 23.4 Flask security is application-specific

Flask's security documentation highlights resource limits, XSS, CSRF,
security headers, cookie settings and trusted-host configuration. Select
the relevant controls for this API and frontend deployment; do not
assume Flask enables every application security control automatically.

Reference: - https://flask.palletsprojects.com/en/stable/web-security/

### 23.5 API threat modelling

Use the OWASP API Security Top 10 to structure endpoint-level threat
review, particularly object-level authorization, authentication,
property-level authorization, unrestricted resource consumption,
function-level authorization, sensitive business flows, security
misconfiguration and improper API inventory.

Reference: - https://owasp.org/www-project-api-security/

### 23.6 Scope of web research

The official documentation above validates implementation guidance, not
the current state of the user's codebase. No live repository inspection,
Supabase schema inspection, hardware test, penetration test or
restaurant pilot was performed as part of producing this design file.
All implementation-status claims must therefore be verified against the
actual project.

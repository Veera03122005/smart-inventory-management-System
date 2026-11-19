# SmartStock AI — Capabilities & Verification Status Matrix

> **Reference**: Cross-verified against `README_SmartStock_AI.md` Section 27 (*Implementation status*), codebase inspection, and regression tests in `backend/tests/test_api_baseline.py`.
>
> **Strict Verification Standard**:
> - `Implemented`: Fully backed by database schema, backend endpoints, business logic, and automated tests.
> - `Partial`: Feature partially implemented (e.g., UI exists without backend persistence, simulated/firmware exists without hardware CI, or in-place updates without double-entry journal).
> - `Missing`: No database support, no backend API, or no implementation in the codebase.

---

## 1. Capability Verification Matrix

| # | Capability | Target Requirement | Status | Proving Files & Tests | Technical Evaluation & Evidence Summary |
|---|---|---|:---:|---|---|
| 1 | **Authentication** | Backend tests and session review | **Implemented** | `backend/app.py:login`<br>`backend/app.py:me`<br>`frontend/src/api.ts`<br>`backend/tests/test_api_baseline.py:test_01-06` | URLSafeTimedSerializer JWT token signing (`TOKEN_HOURS = 12`), salted password hashing (`generate_password_hash` / `check_password_hash`), token expiration and bad signature rejection. Verified with unit tests for valid login, invalid password, nonexistent user, and empty payload. |
| 2 | **Owner/manager/staff permissions** | Permission and negative-access tests | **Implemented** | `backend/app.py:@auth`<br>`backend/tests/test_api_baseline.py:test_07-11` | Strict role-based access control (RBAC) enforced on the backend via `@auth(*roles)` decorator. Owner owns user management (`/api/users`); Manager controls reports, simulator, model retraining, and alert acknowledgement; Staff is restricted to read-only dashboard/readings and operator workflows (refill, manual stock sheet). Negative-access tests verify HTTP 403 Forbidden responses. |
| 3 | **Multi-restaurant isolation** | Cross-tenant integration tests | **Missing** | `backend/db.py`<br>`backend/app.py` | Schema (`db.py`) has no `restaurant_id` column on any table (`users`, `ingredients`, `devices`, `iot_readings`, `refill_sessions`, `manual_entries`). The backend operates as a single-restaurant system with no tenant boundaries or tenant isolation tests. |
|
| 4 | **Inventory ledger** | Reconciliation and concurrency tests | **Partial** | `backend/db.py`<br>`backend/app.py:manual_save`<br>`backend/tests/test_api_baseline.py:test_15` | Daily register (`manual_entries`) and refill logs (`refill_sessions`) exist, but transactions update `closing_stock` in place (`ON CONFLICT(date, ingredient_id) DO UPDATE SET ...`). The system lacks an immutable double-entry ledger, explicit reversal/adjustment transactions, and formal concurrency reconciliation. |
| 5 | **Stock-in and refill** | End-to-end transaction tests | **Implemented** | `backend/iot.py`<br>`backend/app.py:refill_*`<br>`frontend/src/pages/Refill.tsx`<br>`backend/tests/test_api_baseline.py:test_16` | Barcode tare-locking session workflow (`/api/refill/open`, `/complete`, `/cancel`). Enforces minimum refill weight threshold (`REFILL_MIN_KG = 0.2 kg`, returning HTTP 422 if threshold not reached), prevents concurrent open sessions per device (HTTP 409 Conflict), and injects `REFILL_START` / `REFILL_END` markers into the IoT timeline. |
| 6 | **IoT telemetry** | Actual ESP32 integration tests | **Partial** | `esp32/smartstock_esp32/smartstock_esp32.ino`<br>`backend/iot.py:ingest`<br>`backend/simulator.py`<br>`backend/tests/test_api_baseline.py:test_17` | ESP32 C++ firmware sketch is implemented for HX711 load-cell sensors. Backend endpoint (`POST /api/iot/readings`) verifies API keys (`X-Device-Key`), rejects duplicates, and handles live streaming. Live simulator runs successfully, but physical hardware CI integration tests are not connected. |
| 7 | **Barcode workflows** | Device/browser tests | **Implemented** | `backend/iot.py:resolve_barcode`<br>`backend/app.py:barcode`<br>`frontend/src/pages/Refill.tsx`<br>`backend/tests/test_api_baseline.py:test_14` | Barcode lookup via `/api/barcode/<code>` mapped to unique ingredient barcodes. Frontend supports manual entry, one-click demo fill, and camera-based scanning via html5-qrcode. Tested for valid lookup (200) and unknown barcode (404). |
| 8 | **Excel/PDF upload** | Representative file test corpus | **Missing** | `backend/app.py` | CSV export is supported (`GET /api/reports/<name>.csv`), but no backend endpoint or file ingestion parser exists for uploading or processing Excel (.xlsx) workbooks or PDF files into the inventory register. |
| 9 | **OCR and document review** | Extraction accuracy and review tests | **Missing** | `backend/`, `frontend/` | No OCR engine (e.g. Tesseract, Google Vision API, or local pipeline), image extraction pipeline, or document staging/review interface exists. |
| 10 | **AI analytics/forecasting** | Model evaluation and provenance | **Implemented** | `backend/ml.py`<br>`backend/tools/baseline_metrics.py`<br>`docs/baseline_metrics.md`<br>`backend/tests/test_api_baseline.py:test_12,18` | Unified daily time series constructed from dual channels (load-cell drops + manual stock register with weekday profile reconstruction). Automated comparison of 4 models (Seasonal Naive, 7d Moving Average, Random Forest, XGBoost) on a 60-day validation window. Tracks data provenance (`entered`, `reconstructed`, `iot`), computes WAPE/MAE/RMSE, estimates safety stock ($Z = 2.05$), flags FIFO batch expiry risk, and detects usage anomalies. |
| 11 | **Independent POS** | Tests proving no inventory coupling | **Missing** | `backend/`, `frontend/` | No point-of-sale (POS) billing engine, receipt printer interface, or register module exists. Ground rule compliance: no inventory coupling from sales currently exists because POS is entirely absent. |
| 12 | **PWA/offline drafts** | Real mobile and reconnect tests | **Missing** | `frontend/` | The frontend is a standard single-page application (React 18 + Vite). It lacks a Web App Manifest (`manifest.webmanifest`), service worker for offline asset caching, and an IndexedDB/LocalStorage queue for offline stock sheet drafts. |
| 13 | **Production security** | Security review and deployment checks | **Partial** | `backend/app.py`<br>`backend/tests/test_api_baseline.py:test_01-11,20-22` | Uses parameterized SQL (preventing SQL injection), salted password hashing, and token signature validation. However, `SMARTSTOCK_SECRET` falls back to an insecure hardcoded default (`change-me-in-production`), CORS allows all origins (`*`), and tokens are accepted in URL query strings for report downloads (`/api/reports/...`). |

---

## 2. Summary Statistics

| Status | Count | Percentage | Capabilities |
|:---:|:---:|:---:|---|
| **Implemented** | 5 | 38.5% | Authentication, Owner/manager/staff permissions, Stock-in and refill, Barcode workflows, AI analytics/forecasting |
| **Partial** | 3 | 23.1% | Inventory ledger, IoT telemetry, Production security |
| **Missing** | 5 | 38.5% | Multi-restaurant isolation, Excel/PDF upload, OCR and document review, Independent POS, PWA/offline drafts |
| **Total** | **13** | **100%** | |

---

## 3. Detailed Gap Analysis & Recommendations

### Ledger Immutability (Capability 4)
- **Current Defect**: `manual_save` performs an upsert (`INSERT ... ON CONFLICT DO UPDATE`) directly mutating existing closing stock records.
- **Required Fix**: Move to an append-only journal table (`inventory_transactions`) recording event timestamp, capture channel (`MANUAL_FORM`, `BARCODE`, `IOT_INGESTION`), quantity change, and unit cost. Derive balances from the event sum.

### Production Security Hardening (Capability 13)
- **Current Defect**: Default secret key `"change-me-in-production"`; permissive CORS configuration.
- **Required Fix**: Fail on startup in production if `SMARTSTOCK_SECRET` is unset; restrict CORS to authorized domains; migrate CSV report downloads completely to `Authorization` Bearer headers (remove token query parameter support).

### Multi-Tenancy (Capability 3)
- **Current Defect**: Single-restaurant hardcoding throughout SQLite schema.
- **Required Fix**: Introduce `restaurants` table and enforce `restaurant_id` foreign keys on all core entities with tenant-scoped query filters.

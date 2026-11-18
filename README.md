# SmartStock AI

Inventory intelligence for restaurant kitchens. Two data channels feed one ledger:

- **IoT channel** - load cell + HX711 + ESP32 weighing units (a built-in simulator stands in until the hardware is ready)
- **Manual channel** - the daily stock sheet

Machine learning (Random Forest and XGBoost, checked against two simple baselines) forecasts each
ingredient's requirement, recommends order quantities, and flags expiry risk and unusual usage.

## Run it (two commands)

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. The first start creates the database from `backend/data/*.csv` and trains
the models (10-20 seconds).

| Login | Password | Can do |
|---|---|---|
| staff | staff123 | dashboard, live IoT, barcode refill, stock sheet, view alerts |
| manager | manager123 | + AI forecast, reports, simulator control, acknowledge alerts |
| owner | owner123 | + user management |

### Frontend development (optional)

The built frontend is already in `frontend/dist` and is served by Flask. To change the UI:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to Flask on :5000
npm run build      # refresh frontend/dist
```

## Demo script (about 4 minutes)

1. **Dashboard** (manager): today's plan - stock, days of cover, AI "prepare" quantity, order quantity, alerts.
2. **Live IoT**: press *Start simulator*. Three bins start reporting. Press *Simulate a 2 kg spill* on one bin, then open **Alerts** - a "Sudden weight drop" alert appears.
3. **Barcode refill**: click *Onion* (fills in its barcode), *Open refill session*, wait a few seconds while the bin fills, *Complete refill*. The added weight is logged as a REFILL, not as usage.
4. **Stock sheet**: pick Chicken, enter received / used, save. Closing stock is calculated; forecasts refresh.
5. **AI forecast**: model comparison table (WAPE of four models), validation chart, 7-day forecast, reorder point, expiry-risk batches (see Mutton).
6. **Reports**: download any CSV. Sign in as *staff* to show that Forecast, Reports and Users are hidden and blocked by the API.

## The datasets (`backend/data/`)

| File | What it is |
|---|---|
| `manual_stock_register.csv` | Daily stock sheet for 6 ingredients, 1 Aug 2025 onwards. Includes missed days (about 7%), rounding, entry slips, batches, expiry and wastage. |
| `iot_readings.csv` | 5-minute load-cell readings for the rice, oil and onion bins for the last 30 days, with barcode refill events, Wi-Fi outages, unstable readings and one oil spill. |
| `refill_sessions.csv` | Barcode refill sessions matching the IoT log. |
| `true_daily_demand.csv` | The simulated true usage. Not used by the app; used only to score the models in the paper. |
| `ingredients.csv` | Ingredient master: unit, barcode, shelf life, lead time, cost. |

**The data is simulated** (weekday peaks, festivals, Purattasi month, growth, catering days). Regenerate it so
that it ends yesterday, then rebuild the database:

```bash
cd backend
python generate_data.py            # optional: --end 2026-11-15 --seed 42 --iot-days 30
python seed_db.py --fresh
python app.py
```

## Connecting the real ESP32

1. Open `esp32/smartstock_esp32/smartstock_esp32.ino` in the Arduino IDE, install the *HX711* (Bogdan Necula) and *ArduinoJson* libraries.
2. Set Wi-Fi name/password, the laptop's IP in `API_URL`, and calibrate `CAL_FACTOR` (steps are in the sketch).
3. Run Flask on the laptop (same Wi-Fi). The device posts to `POST /api/iot/readings` with header `X-Device-Key`.
   Device IDs and keys are in `backend/seed_db.py` (`DEVICE_KEYS`).
4. Stop the simulator. The Live IoT page shows the real readings.

## Project layout

```
backend/
  app.py            Flask REST API (auth, dashboard, alerts, stock sheet, IoT, refill, reports)
  ml.py             daily series from both channels, RF/XGBoost training, forecast, reorder, expiry, anomalies
  iot.py            reading ingestion (device key, duplicate rejection), barcode refill sessions, spill check
  simulator.py      live IoT simulator (uses the same ingestion path as a real device)
  db.py             SQLite schema and helpers          seed_db.py   loads the CSVs
  generate_data.py  dataset generator                  calendar_tn.py  festivals and Purattasi dates
frontend/           React + TypeScript + Tailwind + Recharts
esp32/              firmware for the weighing unit
docs/supabase_schema.sql   same schema for Supabase/PostgreSQL
paper_experiments/  script that produces every number in the research paper
```

## API quick reference

`POST /api/auth/login` · `GET /api/dashboard` · `GET /api/forecast` · `POST /api/forecast/retrain` ·
`GET /api/alerts` · `GET|POST /api/manual-entries` · `POST /api/iot/readings` (device) · `GET /api/iot/devices` ·
`GET /api/iot/readings?device_id=` · `POST /api/iot/simulator/{start|stop|spill}` · `POST /api/refill/open` ·
`POST /api/refill/{id}/complete` · `GET /api/reports/{name}.csv` · `GET|POST /api/users`

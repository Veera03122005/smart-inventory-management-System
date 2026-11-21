-- 001_initial_schema.sql: Baseline initial schema for SmartStock AI
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner','manager','staff')),
  full_name TEXT
);

CREATE TABLE IF NOT EXISTS ingredients (
  ingredient_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  unit TEXT NOT NULL,
  shelf_life_days INTEGER NOT NULL,
  lead_time_days INTEGER NOT NULL,
  unit_cost_rs REAL NOT NULL,
  barcode TEXT UNIQUE NOT NULL,
  iot_enabled INTEGER NOT NULL DEFAULT 0,
  device_id TEXT,
  min_stock REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS devices (
  device_id TEXT PRIMARY KEY,
  ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
  api_key TEXT NOT NULL,
  last_seen TEXT,
  last_seq INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS iot_readings (
  reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL REFERENCES devices(device_id),
  ingredient_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  weight_kg REAL NOT NULL CHECK (weight_kg >= 0),
  stable INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  session_id TEXT,
  seq_no INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'history',
  UNIQUE (device_id, seq_no, source)
);

CREATE INDEX IF NOT EXISTS ix_read_dev_ts ON iot_readings(device_id, ts);

CREATE TABLE IF NOT EXISTS refill_sessions (
  session_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  ingredient_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  weight_before_kg REAL,
  weight_after_kg REAL,
  refill_kg REAL,
  batch_no TEXT,
  expiry_date TEXT,
  scanned_by TEXT,
  status TEXT NOT NULL CHECK (status IN ('OPEN','COMPLETED','REJECTED','CANCELLED')),
  reason TEXT
);

CREATE TABLE IF NOT EXISTS manual_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
  opening_stock REAL,
  received_qty REAL,
  batch_no TEXT,
  expiry_date TEXT,
  used_qty REAL,
  wastage_qty REAL,
  wastage_reason TEXT,
  closing_stock REAL,
  days_covered INTEGER,
  entered_by TEXT,
  entry_status TEXT NOT NULL,
  UNIQUE (date, ingredient_id)
);

CREATE TABLE IF NOT EXISTS alert_acks (
  alert_key TEXT PRIMARY KEY,
  acked_by TEXT,
  acked_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  actor TEXT,
  action TEXT,
  detail TEXT
);

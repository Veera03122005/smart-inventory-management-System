-- SmartStock AI - PostgreSQL / Supabase schema (same tables as backend/db.py).
-- Run in the Supabase SQL editor, then point backend/db.py at Postgres (psycopg) instead of SQLite.
create table users (
  id bigint generated always as identity primary key,
  username text unique not null, password_hash text not null,
  role text not null check (role in ('owner','manager','staff')), full_name text);
create table ingredients (
  ingredient_id text primary key, name text not null, unit text not null,
  shelf_life_days int not null, lead_time_days int not null, unit_cost_rs numeric not null,
  barcode text unique not null, iot_enabled boolean not null default false,
  device_id text, min_stock numeric not null default 0);
create table devices (
  device_id text primary key, ingredient_id text not null references ingredients,
  api_key text not null, last_seen timestamptz, last_seq bigint default 0);
create table iot_readings (
  reading_id bigint generated always as identity primary key,
  device_id text not null references devices, ingredient_id text not null,
  ts timestamptz not null, weight_kg numeric not null check (weight_kg >= 0),
  stable boolean not null, event_type text not null, session_id text,
  seq_no bigint not null, source text not null default 'live',
  unique (device_id, seq_no, source));
create index on iot_readings (device_id, ts);
create table refill_sessions (
  session_id text primary key, device_id text not null, ingredient_id text not null,
  started_at timestamptz not null, completed_at timestamptz,
  weight_before_kg numeric, weight_after_kg numeric, refill_kg numeric,
  batch_no text, expiry_date date, scanned_by text,
  status text not null check (status in ('OPEN','COMPLETED','REJECTED','CANCELLED')), reason text);
create table manual_entries (
  id bigint generated always as identity primary key,
  date date not null, ingredient_id text not null references ingredients,
  opening_stock numeric, received_qty numeric, batch_no text, expiry_date date,
  used_qty numeric, wastage_qty numeric, wastage_reason text, closing_stock numeric,
  days_covered int, entered_by text, entry_status text not null,
  unique (date, ingredient_id));
create table alert_acks (alert_key text primary key, acked_by text, acked_at timestamptz);
create table audit_log (id bigint generated always as identity primary key, ts timestamptz, actor text, action text, detail text);
-- Enable row level security on every table and add policies per role before going live.

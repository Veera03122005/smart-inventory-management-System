"""Create the SQLite database and load the datasets.  Usage: python seed_db.py [--fresh]"""
import os, sys
import pandas as pd
from werkzeug.security import generate_password_hash
import db

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEVICE_KEYS = {"ESP32-RICE-01": "rice-key-123", "ESP32-OIL-01": "oil-key-123", "ESP32-ONION-01": "onion-key-123"}
USERS = [("owner", "owner123", "owner", "Restaurant Owner"),
         ("manager", "manager123", "manager", "Kitchen Manager"),
         ("staff", "staff123", "staff", "Kitchen Staff")]


def nz(v):
    return None if pd.isna(v) or v == "" else v


def seed(fresh=False):
    if fresh and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_schema()
    ing = pd.read_csv(os.path.join(DATA, "ingredients.csv"))
    reg = pd.read_csv(os.path.join(DATA, "manual_stock_register.csv"))
    iot = pd.read_csv(os.path.join(DATA, "iot_readings.csv"))
    ses = pd.read_csv(os.path.join(DATA, "refill_sessions.csv"))
    with db.tx() as con:
        for u, p, r, n in USERS:
            con.execute("INSERT OR IGNORE INTO users(username,password_hash,role,full_name) VALUES (?,?,?,?)",
                        (u, generate_password_hash(p), r, n))
        for _, r in ing.iterrows():
            con.execute("INSERT OR REPLACE INTO ingredients VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (r.ingredient_id, r["name"], r.unit, int(r.shelf_life_days), int(r.lead_time_days),
                         float(r.unit_cost_rs), str(r.barcode), int(r.iot_enabled), nz(r.device_id), float(r.min_stock)))
            if nz(r.device_id):
                con.execute("INSERT OR IGNORE INTO devices(device_id, ingredient_id, api_key) VALUES (?,?,?)",
                            (r.device_id, r.ingredient_id, DEVICE_KEYS[r.device_id]))
        con.executemany(
            "INSERT OR IGNORE INTO manual_entries(date,ingredient_id,opening_stock,received_qty,batch_no,expiry_date,"
            "used_qty,wastage_qty,wastage_reason,closing_stock,days_covered,entered_by,entry_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(r.date, r.ingredient_id, nz(r.opening_stock), nz(r.received_qty), nz(r.batch_no), nz(r.expiry_date),
              nz(r.used_qty), nz(r.wastage_qty), nz(r.wastage_reason), nz(r.closing_stock), int(r.days_covered),
              nz(r.entered_by), r.entry_status) for r in reg.itertuples()])
        con.executemany(
            "INSERT OR IGNORE INTO iot_readings(device_id,ingredient_id,ts,weight_kg,stable,event_type,session_id,seq_no,source) "
            "VALUES (?,?,?,?,?,?,?,?, 'history')",
            [(r.device_id, r.ingredient_id, r.timestamp, float(r.weight_kg), int(r.stable), r.event_type,
              nz(r.session_id), int(r.seq_no)) for r in iot.itertuples()])
        con.executemany(
            "INSERT OR IGNORE INTO refill_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
            [(r.session_id, r.device_id, r.ingredient_id, r.started_at, r.completed_at, r.weight_before_kg,
              r.weight_after_kg, r.refill_kg, r.batch_no, r.expiry_date, r.scanned_by, r.status) for r in ses.itertuples()])
        last = iot.groupby("device_id").agg(ts=("timestamp", "max"), seq=("seq_no", "max"))
        for dev, r in last.iterrows():
            con.execute("UPDATE devices SET last_seen=?, last_seq=? WHERE device_id=?", (r.ts, int(r.seq), dev))

        # Initialize inventory_balances and baseline inventory_transactions
        for _, r in ing.iterrows():
            iid = r.ingredient_id
            last_entry = con.execute(
                "SELECT closing_stock, date FROM manual_entries WHERE ingredient_id=? AND entry_status='ENTERED' "
                "AND closing_stock IS NOT NULL ORDER BY date DESC LIMIT 1", (iid,)
            ).fetchone()
            stock = float(last_entry[0]) if last_entry and last_entry[0] is not None else 0.0
            stock_date = last_entry[1] if last_entry else "2026-11-15"
            tx_id = f"TX_INIT_{iid}"
            con.execute(
                "INSERT OR IGNORE INTO inventory_transactions (transaction_id, ingredient_id, quantity, delta_qty, "
                "unit, transaction_type, source_channel, timestamp, actor, notes) "
                "VALUES (?, ?, ?, ?, ?, 'STOCK_COUNT', 'BASELINE_MIGRATION', ?, 'system', 'Baseline stock count')",
                (tx_id, iid, stock, stock, r.unit, f"{stock_date} 23:59:59")
            )
            con.execute(
                "INSERT OR REPLACE INTO inventory_balances (ingredient_id, book_balance, last_transaction_id, last_updated_at) "
                "VALUES (?, ?, ?, ?)",
                (iid, stock, tx_id, f"{stock_date} 23:59:59")
            )
    print("Database ready:", db.DB_PATH)


if __name__ == "__main__":
    seed(fresh="--fresh" in sys.argv)

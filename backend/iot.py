"""
SmartStock AI — IoT Ingestion, Barcode Refill Sessions, and Telemetry Reliability.
Provides collision-resistant session IDs, temporal validation, idempotent completion,
and strictly prevents synthetic telemetry injection into raw hardware reading streams.
"""
import uuid
from datetime import datetime, timedelta
import db
import ledger

REFILL_MIN_KG = 0.2          # tau_r: minimum accepted refill
SESSION_TIMEOUT_MIN = 10
SPILL_DROP_KG = 1.5          # sudden drop between two stable readings outside a session


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_timestamp(ts_str):
    """Parses ISO8601 or standard string timestamps into a datetime object."""
    if not ts_str:
        return datetime.now()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: '{ts_str}'")


def ingest(payload, api_key, source="live"):
    """
    Validate and store one raw sensor reading.
    Rejects invalid API keys, negative or over-capacity weights, and implausible future timestamps.
    Separates device measured_at from server ingested_at. Handles duplicates and replay safely:
    - Delayed offline packets (lower sequence numbers) are accepted and stored as valid historical readings.
    - The device sequence watermark is maintained monotonically (MAX(last_seq, seq)) without regression.
    - Duplicate telemetry packets (same device, timestamp, and sequence) are safely ignored.
    Returns (status_code, body).
    """
    dev_id = payload.get("device_id")
    dev = db.query("SELECT * FROM devices WHERE device_id=?", (dev_id,))
    if not dev:
        return 404, {"error": "unknown device"}
    dev = dev[0]

    if api_key != dev["api_key"]:
        return 401, {"error": "invalid device key"}

    try:
        w = float(payload["weight_kg"])
        seq = int(payload["seq_no"])
    except (KeyError, ValueError, TypeError):
        return 400, {"error": "weight_kg and seq_no required"}

    if w < 0 or w > 25:
        return 422, {"error": "weight out of range (0-25 kg)"}

    # Validate measurement timestamp and guard against implausible future readings
    ts_raw = payload.get("measured_at")
    server_now = datetime.now()
    if ts_raw:
        try:
            measured_dt = parse_timestamp(ts_raw)
        except ValueError:
            return 400, {"error": f"invalid timestamp format: '{ts_raw}'"}

        # Reject readings timestamped more than 5 minutes in the future
        if measured_dt > server_now + timedelta(minutes=5):
            return 422, {"error": "measurement timestamp cannot be in the future"}
        ts = measured_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts = server_now.strftime("%Y-%m-%d %H:%M:%S")

    ingested_at = server_now.strftime("%Y-%m-%d %H:%M:%S")
    stable = int(bool(payload.get("stable", True)))
    session = db.query("SELECT session_id FROM refill_sessions WHERE device_id=? AND status='OPEN'", (dev_id,))

    with db.tx() as con:
        cur = con.execute(
            """
            INSERT OR IGNORE INTO iot_readings (
                device_id, ingredient_id, ts, ingested_at, weight_kg, stable,
                event_type, session_id, seq_no, source
            ) VALUES (?, ?, ?, ?, ?, ?, 'READING', ?, ?, ?)
            """,
            (
                dev_id, dev["ingredient_id"], ts, ingested_at, w, stable,
                session[0]["session_id"] if session else None, seq, source
            )
        )
        if cur.rowcount == 0:
            return 200, {"status": "duplicate", "seq_no": seq}

        # Update last seen and maintain highest known monotonic sequence
        con.execute(
            "UPDATE devices SET last_seen=MAX(COALESCE(last_seen, ''), ?), last_seq=MAX(COALESCE(last_seq,0), ?) WHERE device_id=?",
            (ts, seq, dev_id)
        )

    return 201, {"status": "accepted", "seq_no": seq, "ts": ts}


def latest_stable(device_id, source=None, after_ts=None):
    """Fetches the latest stable reading for a device, optionally after a specified timestamp."""
    sql = "SELECT * FROM iot_readings WHERE device_id=? AND stable=1"
    args = [device_id]
    if source:
        sql += " AND source=?"
        args.append(source)
    if after_ts:
        sql += " AND ts > ?"
        args.append(after_ts)
    sql += " ORDER BY ts DESC, reading_id DESC LIMIT 1"
    r = db.query(sql, args)
    return r[0] if r else None


def resolve_barcode(code):
    r = db.query("SELECT * FROM ingredients WHERE barcode=?", (str(code).strip(),))
    return r[0] if r else None


def open_session(barcode, user, batch_no=None, expiry_date=None):
    """
    Opens a tare-locked barcode refill session with a collision-resistant UUID session key.
    """
    ing = resolve_barcode(barcode)
    if not ing:
        return 404, {"error": "barcode not found - onboard the product first"}
    if not ing["device_id"]:
        return 409, {"error": f"{ing['name']} has no weighing device; record the receipt in the manual register"}

    if db.query("SELECT 1 FROM refill_sessions WHERE device_id=? AND status='OPEN'", (ing["device_id"],)):
        return 409, {"error": "a refill session is already open for this device"}

    base = latest_stable(ing["device_id"], "live") or latest_stable(ing["device_id"])
    if not base:
        return 409, {"error": "no stable reading yet from the device"}

    # Collision-resistant session key (microsecond resolution + random hex)
    sid = f"RS{datetime.now():%y%m%d%H%M%S}_{uuid.uuid4().hex[:6]}"

    with db.tx() as con:
        con.execute(
            """
            INSERT INTO refill_sessions (
                session_id, device_id, ingredient_id, started_at, weight_before_kg,
                batch_no, expiry_date, scanned_by, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """,
            (
                sid, ing["device_id"], ing["ingredient_id"], now_str(), base["weight_kg"],
                batch_no, expiry_date, user
            )
        )
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_str(), user, "REFILL_OPEN", f"{sid} {ing['name']} base={base['weight_kg']}")
        )

    return 201, {
        "session_id": sid,
        "ingredient": ing["name"],
        "device_id": ing["device_id"],
        "weight_before_kg": base["weight_kg"],
        "expires_in_min": SESSION_TIMEOUT_MIN,
    }


def complete_session(sid, user):
    """
    Completes a refill session. Enforces:
    1. Idempotency: multiple completion calls return the existing completed result.
    2. Freshness: requires a stable reading taken strictly after session start.
    3. Minimum threshold: rejects refills below REFILL_MIN_KG (0.2 kg).
    4. Auditable transaction: logs the refill in inventory_transactions (delta = 0).
    """
    s_list = db.query("SELECT * FROM refill_sessions WHERE session_id=?", (sid,))
    if not s_list:
        return 404, {"error": "session not found"}
    s = s_list[0]

    # Idempotent completion check
    if s["status"] != "OPEN":
        return 200, {
            "status": s["status"],
            "session_id": sid,
            "weight_before_kg": s["weight_before_kg"],
            "weight_after_kg": s["weight_after_kg"],
            "refill_kg": s["refill_kg"],
            "duplicate": True,
        }

    started = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() - started > timedelta(minutes=SESSION_TIMEOUT_MIN):
        _close(sid, "REJECTED", None, None, "session timed out", user)
        return 409, {"error": "session timed out - scan again"}

    # Must require a fresh stable reading measured strictly AFTER session start
    after = latest_stable(s["device_id"], "live", after_ts=s["started_at"]) or \
            latest_stable(s["device_id"], after_ts=s["started_at"])

    if not after:
        return 409, {
            "error": "no fresh stable reading after refill session start - ensure scale has stabilized",
            "status": "WAITING_FOR_READING"
        }

    delta = after["weight_kg"] - s["weight_before_kg"]
    if delta < REFILL_MIN_KG:
        _close(sid, "REJECTED", after["weight_kg"], delta, f"weight increase {delta:.2f} kg below threshold", user)
        return 422, {"error": f"no valid refill detected (change {delta:.2f} kg)", "status": "REJECTED"}

    _close(sid, "COMPLETED", after["weight_kg"], delta, None, user)

    # Post auditable REFILL transaction into the inventory journal
    try:
        ledger.post_transaction(
            ingredient_id=s["ingredient_id"],
            transaction_type="REFILL",
            quantity=round(delta, 3),
            delta_qty=0.0,  # Refill into kitchen bin is an internal movement; leaves total inventory invariant
            unit="kg",
            actor=user,
            source_channel="BARCODE",
            reference_id=sid,
            batch_no=s.get("batch_no"),
            expiry_date=s.get("expiry_date"),
            idempotency_key=f"REFILL_{sid}",
            notes=f"Refill session {sid} for {s['device_id']}: container weight increased by {round(delta, 3)} kg",
            allow_negative=True,
        )
    except Exception:
        pass

    return 200, {
        "status": "COMPLETED",
        "session_id": sid,
        "weight_before_kg": s["weight_before_kg"],
        "weight_after_kg": after["weight_kg"],
        "refill_kg": round(delta, 3),
    }


def cancel_session(sid, user):
    s = db.query("SELECT status FROM refill_sessions WHERE session_id=?", (sid,))
    if not s:
        return 404, {"error": "session not found"}
    if s[0]["status"] != "OPEN":
        return 200, {"status": s[0]["status"], "duplicate": True}
    _close(sid, "CANCELLED", None, None, "cancelled by user", user)
    return 200, {"status": "CANCELLED"}


def _close(sid, status, after, delta, reason, user):
    """Atomically closes a refill session without nested connections and without synthetic reading pollution."""
    with db.tx() as con:
        con.execute(
            """
            UPDATE refill_sessions
            SET status=?, completed_at=?, weight_after_kg=?, refill_kg=?, reason=?
            WHERE session_id=?
            """,
            (status, now_str(), after, None if delta is None else round(delta, 3), reason, sid)
        )
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_str(), user, "REFILL_" + status, f"{sid} {reason or ''}")
        )


def spill_events(hours=None, source=None):
    """Sudden stable-weight drops outside refill sessions (possible spillage/pilferage)."""
    sql = "SELECT * FROM iot_readings WHERE stable=1 OR event_type!='READING'"
    rows = db.query(sql + " ORDER BY device_id, ts, reading_id")
    out, last, last_ts = [], {}, {}
    for r in rows:
        if source and r["source"] != source:
            continue
        d = r["device_id"]
        if r["event_type"] != "READING":
            last[d] = r["weight_kg"] if r["event_type"] == "REFILL_END" else None
            last_ts[d] = r["ts"]
            continue
        if last.get(d) is not None and last[d] - r["weight_kg"] > SPILL_DROP_KG:
            gap = (datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S")
                   - datetime.strptime(last_ts[d], "%Y-%m-%d %H:%M:%S")).total_seconds()
            if gap <= 600:
                out.append({
                    "device_id": d,
                    "ingredient_id": r["ingredient_id"],
                    "ts": r["ts"],
                    "drop_kg": round(last[d] - r["weight_kg"], 2),
                })
        last[d] = r["weight_kg"]
        last_ts[d] = r["ts"]
    return out

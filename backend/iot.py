"""IoT ingestion, barcode refill sessions and live sensor checks."""
from datetime import datetime, timedelta
import db

REFILL_MIN_KG = 0.2          # tau_r: minimum accepted refill
SESSION_TIMEOUT_MIN = 10
SPILL_DROP_KG = 1.5          # sudden drop between two stable readings outside a session


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ingest(payload, api_key, source="live"):
    """Validate and store one reading. Returns (status_code, body)."""
    dev_id = payload.get("device_id")
    dev = db.query("SELECT * FROM devices WHERE device_id=?", (dev_id,))
    if not dev:
        return 404, {"error": "unknown device"}
    dev = dev[0]
    if api_key != dev["api_key"]:
        return 401, {"error": "invalid device key"}
    try:
        w = float(payload["weight_kg"]); seq = int(payload["seq_no"])
    except (KeyError, ValueError, TypeError):
        return 400, {"error": "weight_kg and seq_no required"}
    if w < 0 or w > 25:
        return 422, {"error": "weight out of range (0-25 kg)"}
    ts = payload.get("measured_at") or now_str()
    stable = int(bool(payload.get("stable", True)))
    session = db.query("SELECT session_id FROM refill_sessions WHERE device_id=? AND status='OPEN'", (dev_id,))
    with db.tx() as con:
        cur = con.execute("INSERT OR IGNORE INTO iot_readings(device_id,ingredient_id,ts,weight_kg,stable,event_type,"
                          "session_id,seq_no,source) VALUES (?,?,?,?,?,?,?,?,?)",
                          (dev_id, dev["ingredient_id"], ts, w, stable, "READING",
                           session[0]["session_id"] if session else None, seq, source))
        if cur.rowcount == 0:
            return 200, {"status": "duplicate", "seq_no": seq}
        con.execute("UPDATE devices SET last_seen=?, last_seq=MAX(COALESCE(last_seq,0),?) WHERE device_id=?",
                    (ts, seq, dev_id))
    return 201, {"status": "accepted", "seq_no": seq}


def latest_stable(device_id, source=None):
    sql = "SELECT * FROM iot_readings WHERE device_id=? AND stable=1"
    args = [device_id]
    if source:
        sql += " AND source=?"; args.append(source)
    r = db.query(sql + " ORDER BY ts DESC, reading_id DESC LIMIT 1", args)
    return r[0] if r else None


def resolve_barcode(code):
    r = db.query("SELECT * FROM ingredients WHERE barcode=?", (code.strip(),))
    return r[0] if r else None


def open_session(barcode, user, batch_no=None, expiry_date=None):
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
    sid = "RS" + datetime.now().strftime("%y%m%d%H%M%S")
    with db.tx() as con:
        con.execute("INSERT INTO refill_sessions(session_id,device_id,ingredient_id,started_at,weight_before_kg,"
                    "batch_no,expiry_date,scanned_by,status) VALUES (?,?,?,?,?,?,?,?,'OPEN')",
                    (sid, ing["device_id"], ing["ingredient_id"], now_str(), base["weight_kg"], batch_no,
                     expiry_date, user))
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
                    (now_str(), user, "REFILL_OPEN", f"{sid} {ing['name']} base={base['weight_kg']}"))
    return 201, {"session_id": sid, "ingredient": ing["name"], "device_id": ing["device_id"],
                 "weight_before_kg": base["weight_kg"], "expires_in_min": SESSION_TIMEOUT_MIN}


def complete_session(sid, user):
    s = db.query("SELECT * FROM refill_sessions WHERE session_id=?", (sid,))
    if not s:
        return 404, {"error": "session not found"}
    s = s[0]
    if s["status"] != "OPEN":
        return 200, {"status": s["status"], "session_id": sid, "refill_kg": s["refill_kg"], "duplicate": True}
    started = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() - started > timedelta(minutes=SESSION_TIMEOUT_MIN):
        _close(sid, "REJECTED", None, None, "session timed out", user)
        return 409, {"error": "session timed out - scan again"}
    after = latest_stable(s["device_id"], "live") or latest_stable(s["device_id"])
    delta = after["weight_kg"] - s["weight_before_kg"]
    if delta < REFILL_MIN_KG:
        _close(sid, "REJECTED", after["weight_kg"], delta, f"weight increase {delta:.2f} kg below threshold", user)
        return 422, {"error": f"no valid refill detected (change {delta:.2f} kg)", "status": "REJECTED"}
    _close(sid, "COMPLETED", after["weight_kg"], delta, None, user)
    return 200, {"status": "COMPLETED", "session_id": sid, "weight_before_kg": s["weight_before_kg"],
                 "weight_after_kg": after["weight_kg"], "refill_kg": round(delta, 3)}


def cancel_session(sid, user):
    _close(sid, "CANCELLED", None, None, "cancelled by user", user)
    return 200, {"status": "CANCELLED"}


def _close(sid, status, after, delta, reason, user):
    with db.tx() as con:
        con.execute("UPDATE refill_sessions SET status=?, completed_at=?, weight_after_kg=?, refill_kg=?, reason=? "
                    "WHERE session_id=?", (status, now_str(), after, None if delta is None else round(delta, 3), reason, sid))
        if status == "COMPLETED":
            s = db.query("SELECT * FROM refill_sessions WHERE session_id=?", (sid,))[0]
            con.execute("INSERT INTO iot_readings(device_id,ingredient_id,ts,weight_kg,stable,event_type,session_id,"
                        "seq_no,source) VALUES (?,?,?,?,1,'REFILL_START',?,?, 'live')",
                        (s["device_id"], s["ingredient_id"], s["started_at"], s["weight_before_kg"], sid, -int(datetime.now().timestamp())))
            con.execute("INSERT INTO iot_readings(device_id,ingredient_id,ts,weight_kg,stable,event_type,session_id,"
                        "seq_no,source) VALUES (?,?,?,?,1,'REFILL_END',?,?, 'live')",
                        (s["device_id"], s["ingredient_id"], now_str(), after, sid, -int(datetime.now().timestamp()) - 1))
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
                    (now_str(), user, "REFILL_" + status, f"{sid} {reason or ''}"))


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
            if gap <= 600:                       # ignore drops that accumulated over a Wi-Fi outage
                out.append({"device_id": d, "ingredient_id": r["ingredient_id"], "ts": r["ts"],
                            "drop_kg": round(last[d] - r["weight_kg"], 2)})
        last[d] = r["weight_kg"]; last_ts[d] = r["ts"]
    return out

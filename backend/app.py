"""SmartStock AI - Flask REST API.  Run:  python app.py   (http://localhost:5000)"""
import csv, io, os
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash
import db, iot, ml, simulator

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "..", "frontend", "dist")
app = Flask(__name__, static_folder=None)
CORS(app)
SECRET = os.environ.get("SMARTSTOCK_SECRET", "change-me-in-production")
signer = URLSafeTimedSerializer(SECRET)
TOKEN_HOURS = 12


# ------------------------------------------------------------------ auth
def auth(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            tok = request.headers.get("Authorization", "").replace("Bearer ", "") or request.args.get("token", "")
            try:
                user = signer.loads(tok, max_age=TOKEN_HOURS * 3600)
            except (BadSignature, SignatureExpired):
                return jsonify(error="not authenticated"), 401
            if roles and user["role"] not in roles:
                return jsonify(error="not authorised for this action"), 403
            request.user = user
            return fn(*a, **k)
        return wrapper
    return deco


@app.post("/api/auth/login")
def login():
    b = request.get_json(force=True, silent=True) or {}
    u = db.query("SELECT * FROM users WHERE username=?", (b.get("username", ""),))
    if not u or not check_password_hash(u[0]["password_hash"], b.get("password", "")):
        return jsonify(error="invalid username or password"), 401
    user = {"username": u[0]["username"], "role": u[0]["role"], "full_name": u[0]["full_name"]}
    return jsonify(token=signer.dumps(user), user=user)


@app.get("/api/me")
@auth()
def me():
    return jsonify(request.user)


@app.get("/api/users")
@auth("owner")
def users():
    return jsonify(db.query("SELECT id, username, role, full_name FROM users ORDER BY id"))


@app.post("/api/users")
@auth("owner")
def add_user():
    b = request.get_json(force=True)
    if b.get("role") not in ("owner", "manager", "staff") or not b.get("username") or len(b.get("password", "")) < 6:
        return jsonify(error="username, role and a password of 6+ characters are required"), 422
    try:
        with db.tx() as con:
            con.execute("INSERT INTO users(username,password_hash,role,full_name) VALUES (?,?,?,?)",
                        (b["username"], generate_password_hash(b["password"]), b["role"], b.get("full_name", "")))
    except Exception:
        return jsonify(error="username already exists"), 409
    return jsonify(status="created"), 201


# ------------------------------------------------------------------ master data
@app.get("/api/health")
def health():
    return jsonify(status="ok", time=datetime.now().isoformat(timespec="seconds"))


@app.get("/api/ingredients")
@auth()
def ingredients():
    return jsonify(db.query("SELECT * FROM ingredients ORDER BY ingredient_id"))


@app.get("/api/barcode/<code>")
@auth()
def barcode(code):
    ing = iot.resolve_barcode(code)
    return (jsonify(ing), 200) if ing else (jsonify(error="barcode not found"), 404)


# ------------------------------------------------------------------ alerts
def build_alerts():
    res = ml.get_results()["results"]
    acks = {a["alert_key"]: a for a in db.query("SELECT * FROM alert_acks")}
    out = []

    def add(kind, sev, ing, title, detail, date, action):
        key = f"{kind}|{ing}|{date}"
        out.append({"key": key, "type": kind, "severity": sev, "ingredient": ing, "title": title, "detail": detail,
                    "date": date, "action": action, "acknowledged": key in acks,
                    "acked_by": acks.get(key, {}).get("acked_by")})

    for r in res.values():
        u, name = r["unit"], r["name"]
        if r["order_qty"] > 0 and (r["stock"] < r["reorder_point"]):
            sev = "high" if r["stock"] < r["prep_qty"] else "medium"
            add("LOW_STOCK", sev, name, f"{name}: stock below reorder point",
                f"Stock {r['stock']} {u}, reorder point {r['reorder_point']} {u}, forecast for {r['target_date']} is "
                f"{r['prep_qty']} {u}.", r["target_date"], f"Order {r['order_qty']} {u}")
        for b in r["batches"]:
            if b["at_risk_qty"] > 0.5:
                add("EXPIRY_RISK", "high" if b["days_to_expiry"] <= 1 else "medium", name,
                    f"{name}: {b['at_risk_qty']} {u} may expire unused",
                    f"Batch {b['batch_no']} expires {b['expiry_date']} ({b['days_to_expiry']} day(s) left), "
                    f"{b['qty_remaining']} {u} remaining.", b["expiry_date"] + "|" + b["batch_no"],
                    "Use this batch first or reduce the next order")
        for a in r["anomalies"][-5:]:
            more = a["actual"] > a["expected"]
            add("USAGE_ANOMALY", "medium", name, f"{name}: usage {'above' if more else 'below'} normal on {a['date']}",
                f"Recorded {a['actual']} {u}, expected about {a['expected']} {u} (z = {a['z']}).", a["date"],
                "Check for wastage, a bulk order or a wrong entry")
    names = {i["ingredient_id"]: i for i in db.query("SELECT * FROM ingredients")}
    for s in iot.spill_events()[-10:]:
        n = names[s["ingredient_id"]]["name"]
        add("SUDDEN_DROP", "high", n, f"{n}: sudden weight drop of {s['drop_kg']} kg",
            f"Device {s['device_id']} recorded the drop at {s['ts']} with no refill session open.", s["ts"],
            "Check for spillage or unrecorded removal")
    last = db.query("SELECT MAX(date) d FROM manual_entries")[0]["d"]
    for m in db.query("SELECT m.date, i.name FROM manual_entries m JOIN ingredients i USING (ingredient_id) "
                      "WHERE m.entry_status='MISSED' AND m.date=?", (last,)):
        add("MISSED_ENTRY", "low", m["name"], f"{m['name']}: stock sheet not filled for {m['date']}",
            "The forecast is using a reconstructed value for this day.", m["date"], "Enter the stock sheet")
    if simulator.status()["running"]:
        for dev, w in simulator.status()["weights"].items():
            d = db.query("SELECT i.name FROM devices d JOIN ingredients i USING (ingredient_id) WHERE d.device_id=?", (dev,))
            if w < 3.0 and not db.query("SELECT 1 FROM refill_sessions WHERE device_id=? AND status='OPEN'", (dev,)):
                add("REFILL_NEEDED", "medium", d[0]["name"], f"{d[0]['name']} bin is low ({w:.1f} kg)",
                    f"Device {dev} live weight is below 3 kg.", datetime.now().strftime("%Y-%m-%d %H"),
                    "Scan the barcode and refill the bin")
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: (a["acknowledged"], order[a["severity"]], a["date"]), reverse=False)
    return out


@app.get("/api/alerts")
@auth()
def alerts():
    return jsonify(build_alerts())


@app.post("/api/alerts/ack")
@auth("owner", "manager")
def ack():
    key = (request.get_json(force=True) or {}).get("key")
    with db.tx() as con:
        con.execute("INSERT OR REPLACE INTO alert_acks VALUES (?,?,?)", (key, request.user["username"], iot.now_str()))
    return jsonify(status="acknowledged")


# ------------------------------------------------------------------ dashboard & forecast
@app.get("/api/dashboard")
@auth()
def dashboard():
    c = ml.get_results()
    res = c["results"]
    al = [a for a in build_alerts() if not a["acknowledged"]]
    rows = []
    for r in res.values():
        status = "OK"
        if any(a["ingredient"] == r["name"] and a["type"] == "LOW_STOCK" for a in al): status = "Low stock"
        elif any(a["ingredient"] == r["name"] and a["type"] == "EXPIRY_RISK" for a in al): status = "Expiry risk"
        rows.append({k: r[k] for k in ("ingredient_id", "name", "unit", "stock", "stock_date", "days_of_cover",
                                       "prep_qty", "target_date", "order_qty", "reorder_point", "model")} | {"status": status})
    cost = {i["ingredient_id"]: i["unit_cost_rs"] for i in db.query("SELECT * FROM ingredients")}
    week = (datetime.strptime(next(iter(res.values()))["stock_date"], "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
    w = db.query("SELECT ingredient_id, SUM(wastage_qty) q, SUM(used_qty) u FROM manual_entries WHERE date>=? GROUP BY 1", (week,))
    return jsonify({
        "run_at": c["run_at"], "target_date": next(iter(res.values()))["target_date"],
        "cards": {"ingredients": len(rows), "low_stock": sum(r["status"] == "Low stock" for r in rows),
                  "expiry_risk": sum(a["type"] == "EXPIRY_RISK" for a in al), "open_alerts": len(al),
                  "stock_value_rs": round(sum(r["stock"] * cost[r["ingredient_id"]] for r in rows)),
                  "order_value_rs": round(sum(r["order_qty"] * cost[r["ingredient_id"]] for r in rows)),
                  "wastage_7d_rs": round(sum((x["q"] or 0) * cost[x["ingredient_id"]] for x in w)),
                  "usage_7d_rs": round(sum((x["u"] or 0) * cost[x["ingredient_id"]] for x in w))},
        "rows": rows, "alerts": al[:6]})


@app.get("/api/forecast")
@auth()
def forecast():
    c = ml.get_results()
    return jsonify({"run_at": c["run_at"], "seconds": c.get("seconds"), "results": list(c["results"].values())})


@app.post("/api/forecast/retrain")
@auth("owner", "manager")
def retrain():
    c = ml.train_all()
    return jsonify(run_at=c["run_at"], seconds=c["seconds"])


# ------------------------------------------------------------------ manual stock sheet
@app.get("/api/manual-entries")
@auth()
def manual_list():
    ing = request.args.get("ingredient_id"); limit = int(request.args.get("limit", 60))
    sql = "SELECT m.*, i.name, i.unit FROM manual_entries m JOIN ingredients i USING (ingredient_id)"
    args = []
    if ing:
        sql += " WHERE m.ingredient_id=?"; args.append(ing)
    return jsonify(db.query(sql + " ORDER BY m.date DESC, m.ingredient_id LIMIT ?", args + [limit]))


@app.get("/api/manual-entries/prefill")
@auth()
def manual_prefill():
    ing = request.args["ingredient_id"]
    stock, d = ml.current_stock(ing)
    nxt = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if d else datetime.now().strftime("%Y-%m-%d")
    r = ml.get_results()["results"].get(ing, {})
    return jsonify(date=nxt, opening_stock=stock, suggested_used=r.get("prep_qty"))


@app.post("/api/manual-entries")
@auth()
def manual_save():
    b = request.get_json(force=True)
    try:
        opening, received = float(b["opening_stock"]), float(b.get("received_qty") or 0)
        used, waste = float(b["used_qty"]), float(b.get("wastage_qty") or 0)
        date, ing = b["date"], b["ingredient_id"]
        datetime.strptime(date, "%Y-%m-%d")
    except (KeyError, ValueError, TypeError):
        return jsonify(error="date, ingredient, opening stock and used quantity are required"), 422
    if min(opening, received, used, waste) < 0:
        return jsonify(error="quantities cannot be negative"), 422
    closing = opening + received - used - waste
    if closing < -0.01:
        return jsonify(error=f"used + wastage ({used + waste}) is more than opening + received ({opening + received})"), 422
    if received > 0 and not b.get("expiry_date"):
        return jsonify(error="expiry date is required when stock is received"), 422
    # days covered: count immediately preceding MISSED days
    prev = db.query("SELECT date, entry_status FROM manual_entries WHERE ingredient_id=? AND date<? ORDER BY date DESC LIMIT 10", (ing, date))
    gap = 0
    for p in prev:
        if p["entry_status"] == "MISSED": gap += 1
        else: break
    batch = b.get("batch_no") or (f"{ing}-M{date.replace('-', '')}" if received > 0 else None)
    with db.tx() as con:
        con.execute("INSERT INTO manual_entries(date,ingredient_id,opening_stock,received_qty,batch_no,expiry_date,used_qty,"
                    "wastage_qty,wastage_reason,closing_stock,days_covered,entered_by,entry_status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'ENTERED') ON CONFLICT(date,ingredient_id) DO UPDATE SET "
                    "opening_stock=excluded.opening_stock, received_qty=excluded.received_qty, batch_no=excluded.batch_no,"
                    "expiry_date=excluded.expiry_date, used_qty=excluded.used_qty, wastage_qty=excluded.wastage_qty,"
                    "wastage_reason=excluded.wastage_reason, closing_stock=excluded.closing_stock,"
                    "days_covered=excluded.days_covered, entered_by=excluded.entered_by, entry_status='ENTERED'",
                    (date, ing, opening, received, batch, b.get("expiry_date") or None, used, waste,
                     b.get("wastage_reason") or None, round(closing, 2), gap + 1, request.user["username"]))
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
                    (iot.now_str(), request.user["username"], "MANUAL_ENTRY", f"{date} {ing} used={used} closing={closing}"))
    ml.invalidate()
    return jsonify(status="saved", closing_stock=round(closing, 2), days_covered=gap + 1), 201


# ------------------------------------------------------------------ IoT
@app.post("/api/iot/readings")
def iot_ingest():
    code, body = iot.ingest(request.get_json(force=True, silent=True) or {}, request.headers.get("X-Device-Key", ""))
    return jsonify(body), code


@app.get("/api/iot/devices")
@auth()
def iot_devices():
    out = []
    for d in db.query("SELECT d.*, i.name, i.unit FROM devices d JOIN ingredients i USING (ingredient_id)"):
        last = db.query("SELECT * FROM iot_readings WHERE device_id=? ORDER BY ts DESC, reading_id DESC LIMIT 1", (d["device_id"],))
        online = False
        if d["last_seen"]:
            online = (datetime.now() - datetime.strptime(d["last_seen"], "%Y-%m-%d %H:%M:%S")).total_seconds() < 30
        sess = db.query("SELECT session_id FROM refill_sessions WHERE device_id=? AND status='OPEN'", (d["device_id"],))
        out.append({"device_id": d["device_id"], "ingredient_id": d["ingredient_id"], "name": d["name"], "unit": d["unit"],
                    "last_seen": d["last_seen"], "online": online, "weight_kg": last[0]["weight_kg"] if last else None,
                    "stable": last[0]["stable"] if last else None, "capacity_kg": 15,
                    "open_session": sess[0]["session_id"] if sess else None})
    return jsonify(out)


@app.get("/api/iot/readings")
@auth()
def iot_readings():
    dev = request.args["device_id"]; limit = int(request.args.get("limit", 200))
    live = db.query("SELECT ts, weight_kg, stable, event_type, session_id FROM iot_readings WHERE device_id=? AND source='live' "
                    "ORDER BY ts DESC, reading_id DESC LIMIT ?", (dev, limit))
    if len(live) >= 5:
        return jsonify(mode="live", readings=list(reversed(live)))
    day = db.query("SELECT MAX(substr(ts,1,10)) d FROM iot_readings WHERE device_id=? AND source='history'", (dev,))[0]["d"]
    hist = db.query("SELECT ts, weight_kg, stable, event_type, session_id FROM iot_readings WHERE device_id=? AND "
                    "source='history' AND substr(ts,1,10)=? ORDER BY ts, reading_id", (dev, day))
    return jsonify(mode="history", day=day, readings=hist)


@app.get("/api/iot/daily")
@auth()
def iot_daily():
    df = ml.iot_daily_usage()
    return jsonify(df.to_dict("records"))


@app.get("/api/iot/simulator")
@auth()
def sim_status():
    return jsonify(simulator.status())


@app.post("/api/iot/simulator/<action>")
@auth("owner", "manager")
def sim_action(action):
    b = request.get_json(force=True, silent=True) or {}
    if action == "start": return jsonify(simulator.start(b.get("interval", 2.0)))
    if action == "stop": return jsonify(simulator.stop())
    if action == "spill": return jsonify(simulator.inject_spill(b.get("device_id")))
    return jsonify(error="unknown action"), 404


# ------------------------------------------------------------------ barcode refill sessions
@app.post("/api/refill/open")
@auth()
def refill_open():
    b = request.get_json(force=True)
    code, body = iot.open_session(b.get("barcode", ""), request.user["username"], b.get("batch_no"), b.get("expiry_date"))
    return jsonify(body), code


@app.post("/api/refill/<sid>/complete")
@auth()
def refill_complete(sid):
    code, body = iot.complete_session(sid, request.user["username"])
    return jsonify(body), code


@app.post("/api/refill/<sid>/cancel")
@auth()
def refill_cancel(sid):
    code, body = iot.cancel_session(sid, request.user["username"])
    return jsonify(body), code


@app.get("/api/refill/sessions")
@auth()
def refill_sessions():
    return jsonify(db.query("SELECT r.*, i.name FROM refill_sessions r JOIN ingredients i USING (ingredient_id) "
                            "ORDER BY started_at DESC LIMIT ?", (int(request.args.get("limit", 25)),)))


# ------------------------------------------------------------------ reports (CSV)
def _csv(rows, name):
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}_{datetime.now():%Y%m%d}.csv"})


@app.get("/api/reports/<name>.csv")
@auth("owner", "manager")
def report(name):
    res = ml.get_results()["results"]
    if name == "stock_summary":
        rows = [{"ingredient": r["name"], "unit": r["unit"], "stock": r["stock"], "stock_date": r["stock_date"],
                 "days_of_cover": r["days_of_cover"], "reorder_point": r["reorder_point"]} for r in res.values()]
    elif name == "forecast_reorder":
        rows = [{"ingredient": r["name"], "unit": r["unit"], "model": r["model"], "date": f["date"], "forecast": f["qty"],
                 "low": f["low"], "high": f["high"], "order_qty_today": r["order_qty"]} for r in res.values() for f in r["forecast"]]
    elif name == "model_evaluation":
        rows = [{"ingredient": r["name"], "model": m, **v, "selected": m == r["model"]} for r in res.values()
                for m, v in r["validation"].items()]
    elif name == "wastage":
        rows = db.query("SELECT m.date, i.name ingredient, i.unit, m.wastage_qty, m.wastage_reason, "
                        "ROUND(m.wastage_qty*i.unit_cost_rs,0) value_rs FROM manual_entries m JOIN ingredients i "
                        "USING (ingredient_id) WHERE m.wastage_qty>0 ORDER BY m.date DESC")
    elif name == "manual_register":
        rows = db.query("SELECT m.date, i.name ingredient, i.unit, m.opening_stock, m.received_qty, m.batch_no, m.expiry_date,"
                        " m.used_qty, m.wastage_qty, m.wastage_reason, m.closing_stock, m.days_covered, m.entered_by,"
                        " m.entry_status FROM manual_entries m JOIN ingredients i USING (ingredient_id) ORDER BY m.date DESC")
    elif name == "iot_daily_usage":
        rows = ml.iot_daily_usage().to_dict("records")
    elif name == "refill_sessions":
        rows = db.query("SELECT * FROM refill_sessions ORDER BY started_at DESC")
    else:
        return jsonify(error="unknown report"), 404
    return _csv(rows, name)


# ------------------------------------------------------------------ built frontend (optional single-port demo)
@app.get("/")
@app.get("/<path:path>")
def spa(path="index.html"):
    if not os.path.isdir(DIST):
        return jsonify(message="SmartStock AI API is running. Start the frontend with `npm run dev` in /frontend."), 200
    full = os.path.join(DIST, path)
    return send_from_directory(DIST, path if os.path.isfile(full) else "index.html")


if __name__ == "__main__":
    if not os.path.exists(db.DB_PATH):
        import seed_db
        seed_db.seed()
    db.init_schema()
    print("Training forecasting models (first start takes ~10-20 s)...")
    ml.get_results()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)

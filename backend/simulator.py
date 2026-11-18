"""
Live IoT simulator. Replays the behaviour of the three ESP32 weighing units through the SAME
ingestion path a real device uses. Each tick = one 5-minute kitchen slot (default every 2 s).
When a barcode refill session is open, the simulated staff member pours stock into the bin.
"""
import threading, time, random
from datetime import datetime
import numpy as np
import db, iot

_state = {"running": False, "tick": 0, "interval": 2.0, "thread": None, "spill": set(), "weights": {}, "slot": 0}
SLOTS = 192        # 07:00-23:00 in 5-minute slots
_hours = 7 + np.arange(SLOTS) * 5 / 60
_prof = 0.3 + 2.2 * np.exp(-((_hours - 13.5) / 1.2) ** 2) + 2.6 * np.exp(-((_hours - 20.5) / 1.3) ** 2)
_prof = _prof / _prof.sum()


def status():
    return {"running": _state["running"], "tick": _state["tick"], "interval": _state["interval"],
            "kitchen_time": f"{7 + _state['slot'] * 5 // 60:02d}:{_state['slot'] * 5 % 60:02d}",
            "weights": {k: round(v, 3) for k, v in _state["weights"].items()}}


def _daily_usage(ingredient_id):
    try:
        import ml
        r = ml.get_results()["results"].get(ingredient_id)
        if r:
            return r["prep_qty"]
    except Exception:
        pass
    return 20.0


def _loop():
    devs = db.query("SELECT * FROM devices")
    seqs = {d["device_id"]: (d["last_seq"] or 0) + 1000 for d in devs}
    for d in devs:
        last = iot.latest_stable(d["device_id"])
        _state["weights"].setdefault(d["device_id"], min(14.0, last["weight_kg"] if last else 12.0))
    usage = {d["device_id"]: _daily_usage(d["ingredient_id"]) for d in devs}
    while _state["running"]:
        slot = _state["slot"]
        for d in devs:
            dev = d["device_id"]
            w = _state["weights"][dev]
            open_s = db.query("SELECT * FROM refill_sessions WHERE device_id=? AND status='OPEN'", (dev,))
            if open_s and w < 13.0:
                w = 13.0 + random.uniform(0.5, 1.5)          # staff pours a sack / tin into the bin
            else:
                w -= usage[dev] * _prof[slot] * random.uniform(0.6, 1.4)
                if dev in _state["spill"]:
                    w -= 2.0; _state["spill"].discard(dev)
            w = max(w, 0.0)
            _state["weights"][dev] = w
            stable = random.random() > 0.03
            seqs[dev] += 1
            iot.ingest({"device_id": dev, "seq_no": seqs[dev], "stable": stable,
                        "weight_kg": round(max(0.0, w + (random.gauss(0, 0.008) if stable else random.gauss(0, 0.15))), 3),
                        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, d["api_key"])
        _state["tick"] += 1
        _state["slot"] = (slot + 1) % SLOTS
        time.sleep(_state["interval"])


def start(interval=2.0):
    if _state["running"]:
        return status()
    _state["interval"] = max(0.5, float(interval))
    _state["running"] = True
    _state["thread"] = threading.Thread(target=_loop, daemon=True)
    _state["thread"].start()
    return status()


def stop():
    _state["running"] = False
    return status()


def inject_spill(device_id):
    _state["spill"].add(device_id)
    return status()

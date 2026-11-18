"""
SmartStock AI - dataset generator.

Creates the two project datasets for one mid-sized non-veg restaurant in Tamil Nadu:

  data/manual_stock_register.csv  daily stock sheet (manual channel) for all ingredients
  data/iot_readings.csv           load-cell readings for the sensor-equipped bins (last N days)
  data/true_daily_demand.csv      ground-truth daily usage (simulation only, used for evaluation)
  data/ingredients.csv            ingredient master (barcodes, shelf life, lead time, cost)

The data is SIMULATED. Patterns: weekday peaks, festivals, Purattasi month, growth trend,
random catering orders, staff entry gaps/rounding/errors, sensor noise, refill sessions.

Usage:  python generate_data.py [--end YYYY-MM-DD] [--iot-days 30] [--seed 42]
"""
import argparse, os
from datetime import date, timedelta
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

INGREDIENTS = [
    # id, name, unit, base/day, weekend strength, purattasi factor, shelf days, lead days, cost Rs/unit, barcode, iot?
    ("ING01", "Chicken",      "kg", 38, 1.0, 0.55,   2, 1, 220, "8901000000011", False),
    ("ING02", "Mutton",       "kg",  9, 1.0, 0.55,   2, 1, 750, "8901000000028", False),
    ("ING03", "Basmati rice", "kg", 30, 0.6, 0.85, 365, 3, 110, "8901000000035", True),
    ("ING04", "Cooking oil",  "L",  12, 0.5, 0.88, 180, 3, 150, "8901000000042", True),
    ("ING05", "Onion",        "kg", 25, 0.5, 0.88,  14, 1,  35, "8901000000059", True),
    ("ING06", "Tomato",       "kg", 15, 0.5, 0.90,   5, 1,  30, "8901000000066", False),
]
DOW = np.array([0.86, 0.84, 0.90, 0.92, 1.04, 1.22, 1.38])          # Mon..Sun
PURATTASI = [("2025-09-17", "2025-10-16"), ("2026-09-17", "2026-10-17")]
FESTIVALS = {"2025-08-15": 1.20, "2025-10-20": 1.35, "2025-12-31": 1.50, "2026-01-15": 1.25,
             "2026-01-16": 1.30, "2026-03-21": 1.30, "2026-05-27": 1.45, "2026-08-15": 1.20,
             "2026-11-08": 1.35}
BAKRID = "2026-05-27"
STAFF = ["Ravi", "Meena", "Arjun", "Lakshmi"]
WASTE_REASONS = ["Spilled", "Burnt", "Over-prepared", "Quality reject"]


def calendar_flags(d):
    s = d.strftime("%Y-%m-%d")
    pur = any(a <= s <= b for a, b in PURATTASI)
    return pur, FESTIVALS.get(s)


def gen_demand(rng, dates):
    t = np.arange(len(dates)) / 365.0
    rows = []
    for i, d in enumerate(dates):
        pur, fest = calendar_flags(d)
        catering = rng.uniform(1.4, 1.8) if rng.random() < 0.03 else 1.0
        for ing in INGREDIENTS:
            iid, name, unit, base, wk, purf, *_ = ing
            f = 1 + wk * (DOW[d.weekday()] - 1)
            f *= purf if pur else 1.0
            if fest:
                f *= 1 + (fest - 1) * (1.0 if wk == 1.0 else 0.5)
            if name == "Mutton" and d.strftime("%Y-%m-%d") == BAKRID:
                f *= 2.2 / (1 + (FESTIVALS[BAKRID] - 1))
            q = base * f * (1 + 0.08 * t[i]) * rng.lognormal(0, 0.10) * catering
            rows.append((d.strftime("%Y-%m-%d"), iid, name, round(q, 2), int(pur), int(fest is not None)))
    return pd.DataFrame(rows, columns=["date", "ingredient_id", "ingredient", "true_usage", "purattasi", "festival"])


def gen_manual_register(rng, demand):
    """Simulate the kitchen's paper stock sheet with a simple par-level ordering habit."""
    out = []
    for ing in INGREDIENTS:
        iid, name, unit, base, wk, purf, shelf, lead, cost, barcode, iot = ing
        d = demand[demand.ingredient_id == iid].reset_index(drop=True)
        par = base * (1.4 * lead if shelf <= 5 else 1.25 * (lead + 4))     # habit-based par level
        batches = [[par, shelf, f"{iid}-B0000"]]                  # qty, days left, batch no
        pipeline = {}
        bseq = 0
        pending_used = 0.0
        missed_open = None
        for i, r in d.iterrows():
            opening = sum(b[0] for b in batches)
            received, batch_no, expiry = 0.0, "", ""
            if i in pipeline:
                received = pipeline.pop(i)
                bseq += 1
                batch_no = f"{iid}-B{bseq:04d}"
                expiry = (pd.Timestamp(r.date) + pd.Timedelta(days=shelf - 1)).strftime("%Y-%m-%d")
                batches.append([received, shelf, batch_no])
            # issue FIFO
            need = r.true_usage
            for b in batches:
                take = min(b[0], need); b[0] -= take; need -= take
                if need <= 1e-9: break
            used = r.true_usage - need           # unmet demand is a stockout (not recorded as used)
            # ageing and spoilage
            for b in batches: b[1] -= 1
            spoiled = sum(b[0] for b in batches if b[1] <= 0)
            other_waste = round(rng.uniform(0.01, 0.04) * used, 2) if rng.random() < 0.15 else 0.0
            reason = "Expired" if spoiled > 0.05 else (rng.choice(WASTE_REASONS) if other_waste > 0 else "")
            # remove expired, and other waste from the oldest batch
            batches = [b for b in batches if b[1] > 0 and b[0] > 1e-9]
            ow = other_waste
            for b in batches:
                take = min(b[0], ow); b[0] -= take; ow -= take
                if ow <= 1e-9: break
            wastage = round(spoiled + other_waste - ow, 2)
            step0 = 0.5 if unit == "L" or base < 20 else 1.0
            if round(np.round(wastage / step0) * step0, 1) == 0:
                reason = ""
            closing = sum(b[0] for b in batches)
            # habit ordering: order up to par when below par
            on_order = sum(pipeline.values())
            if closing + on_order < par:
                qty = par - closing - on_order
                if rng.random() < 0.04:
                    qty *= 1.4                      # supplier over-delivery / bulk offer
                if name == "Mutton" and i == len(d) - 2:
                    qty += 14.0                     # demo scenario: bulk mutton delivery on the last day
                pipeline[i + lead] = pipeline.get(i + lead, 0.0) + round(qty, 1)
            # ---- what the staff actually write down ----
            missed = rng.random() < 0.08
            step = 0.5 if unit == "L" or base < 20 else 1.0
            est_used = used * (1 + rng.normal(0, 0.06))
            if rng.random() < 0.02:
                est_used *= rng.choice([0.8, 1.2])           # transcription slip
            if missed and i < len(d) - 1:
                pending_used += est_used
                if missed_open is None: missed_open = i
                out.append(dict(date=r.date, ingredient_id=iid, ingredient=name, unit=unit,
                                opening_stock="", received_qty=round(received, 1) if received else "",
                                batch_no=batch_no, expiry_date=expiry, used_qty="", wastage_qty="",
                                wastage_reason="", closing_stock="", days_covered=0,
                                entered_by="", entry_status="MISSED"))
                continue
            days = 1 if missed_open is None else i - missed_open + 1
            used_written = np.round((pending_used + est_used) / step) * step
            out.append(dict(date=r.date, ingredient_id=iid, ingredient=name, unit=unit,
                            opening_stock=round(np.round(opening / step) * step, 1),
                            received_qty=round(received, 1) if received else 0,
                            batch_no=batch_no, expiry_date=expiry,
                            used_qty=round(used_written, 1),
                            wastage_qty=round(np.round(wastage / step) * step, 1), wastage_reason=reason,
                            closing_stock=round(np.round(closing / step) * step, 1),
                            days_covered=days, entered_by=rng.choice(STAFF), entry_status="ENTERED"))
            pending_used, missed_open = 0.0, None
    df = pd.DataFrame(out).sort_values(["date", "ingredient_id"]).reset_index(drop=True)
    return df


def gen_iot(rng, demand, end, days):
    """Load-cell readings for sensor-equipped bins: a stable reading every 5 min, 07:00-23:00."""
    BIN_CAP, REFILL_AT, TARE = 15.0, 3.0, 0.0
    start = pd.Timestamp(end) - pd.Timedelta(days=days - 1)
    rows, sess_rows = [], []
    rid, sid = 0, 0
    devices = {"ING03": "ESP32-RICE-01", "ING04": "ESP32-OIL-01", "ING05": "ESP32-ONION-01"}
    # intraday usage profile (07:00..23:00, 5-min slots) with lunch and dinner peaks
    slots = pd.date_range("07:00", "22:55", freq="5min").time
    prof = np.array([0.3 + 2.2 * np.exp(-((h.hour + h.minute / 60 - 13.5) / 1.2) ** 2)
                     + 2.6 * np.exp(-((h.hour + h.minute / 60 - 20.5) / 1.3) ** 2) for h in slots])
    prof = prof / prof.sum()
    for iid, dev in devices.items():
        name = [x for x in INGREDIENTS if x[0] == iid][0][1]
        w, seq = 12.0, 0
        dd = demand[(demand.ingredient_id == iid) & (pd.to_datetime(demand.date) >= start)
                    & (pd.to_datetime(demand.date) <= pd.Timestamp(end))]
        spill_day = dd.date.iloc[len(dd) // 2] if iid == "ING04" else None     # one anomaly for demo
        for _, r in dd.iterrows():
            use = r.true_usage * prof * rng.dirichlet(np.ones(len(prof)) * 40) * len(prof) / len(prof)
            use = use / use.sum() * r.true_usage
            outage = rng.random() < 0.05
            out_from = rng.integers(20, 150)
            for k, tm in enumerate(slots):
                ts = pd.Timestamp(f"{r.date} {tm}")
                w -= use[k]
                if spill_day == r.date and k == 100:
                    w -= 2.0                                                    # spillage anomaly
                if w < REFILL_AT:                                               # barcode refill session
                    sid += 1
                    before = max(w, 0.0)
                    batch = f"{iid}-B{rng.integers(1000, 9999)}"
                    add = round(BIN_CAP - before - rng.uniform(0, 1.5), 2)
                    seq += 1; rid += 1
                    rows.append((rid, dev, iid, name, ts.strftime("%Y-%m-%d %H:%M:%S"), round(before + rng.normal(0, 0.005), 3), 1, "REFILL_START", f"RS{sid:05d}", seq))
                    w = before + add
                    seq += 1; rid += 1
                    t2 = ts + pd.Timedelta(minutes=2)
                    rows.append((rid, dev, iid, name, t2.strftime("%Y-%m-%d %H:%M:%S"), round(w + rng.normal(0, 0.005), 3), 1, "REFILL_END", f"RS{sid:05d}", seq))
                    sess_rows.append((f"RS{sid:05d}", dev, iid, name, ts.strftime("%Y-%m-%d %H:%M:%S"),
                                      t2.strftime("%Y-%m-%d %H:%M:%S"), round(before, 3), round(w, 3), round(add, 3),
                                      batch, (ts + pd.Timedelta(days=[x for x in INGREDIENTS if x[0] == iid][0][6])).strftime("%Y-%m-%d"),
                                      rng.choice(STAFF), "COMPLETED"))
                    continue
                if outage and out_from <= k < out_from + 12:
                    continue                                                    # 1-hour Wi-Fi outage
                seq += 1; rid += 1
                stable = 1 if rng.random() > 0.03 else 0
                noise = rng.normal(0, 0.008) if stable else rng.normal(0, 0.15)
                rows.append((rid, dev, iid, name, ts.strftime("%Y-%m-%d %H:%M:%S"), round(max(w + noise, 0), 3),
                             stable, "READING", "", seq))
    iot = pd.DataFrame(rows, columns=["reading_id", "device_id", "ingredient_id", "ingredient", "timestamp",
                                      "weight_kg", "stable", "event_type", "session_id", "seq_no"])
    sess = pd.DataFrame(sess_rows, columns=["session_id", "device_id", "ingredient_id", "ingredient", "started_at",
                                            "completed_at", "weight_before_kg", "weight_after_kg", "refill_kg",
                                            "batch_no", "expiry_date", "scanned_by", "status"])
    return iot.sort_values(["timestamp", "device_id"]).reset_index(drop=True), sess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-08-01")
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--iot-days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(DATA, exist_ok=True)
    dates = pd.date_range(a.start, a.end, freq="D")
    demand = gen_demand(rng, dates)
    reg = gen_manual_register(rng, demand)
    iot, sess = gen_iot(rng, demand, a.end, a.iot_days)
    ing = pd.DataFrame([dict(ingredient_id=x[0], name=x[1], unit=x[2], shelf_life_days=x[6], lead_time_days=x[7],
                             unit_cost_rs=x[8], barcode=x[9], iot_enabled=int(x[10]),
                             device_id={"ING03": "ESP32-RICE-01", "ING04": "ESP32-OIL-01", "ING05": "ESP32-ONION-01"}.get(x[0], ""),
                             min_stock=round(x[3] * 0.6, 1)) for x in INGREDIENTS])
    demand.to_csv(os.path.join(DATA, "true_daily_demand.csv"), index=False)
    reg.to_csv(os.path.join(DATA, "manual_stock_register.csv"), index=False)
    iot.to_csv(os.path.join(DATA, "iot_readings.csv"), index=False)
    sess.to_csv(os.path.join(DATA, "refill_sessions.csv"), index=False)
    ing.to_csv(os.path.join(DATA, "ingredients.csv"), index=False)
    print(f"Generated {a.start}..{a.end}: register {len(reg)} rows, IoT {len(iot)} readings, "
          f"{len(sess)} refill sessions")


if __name__ == "__main__":
    main()

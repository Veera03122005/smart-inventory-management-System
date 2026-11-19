"""
SmartStock AI — IoT Ingestion & Refill Lifecycle Reliability Tests.
Verifies device authentication, temporal validation, future timestamp rejection,
duplicate and replay handling, fresh post-start reading enforcement, and idempotent refill completion.
"""
from datetime import datetime, timedelta
import time
import pytest
import iot
import db


def test_invalid_device_key(client):
    res = client.post("/api/iot/readings", headers={"X-Device-Key": "wrong-key"}, json={
        "device_id": "ESP32-RICE-01", "weight_kg": 10.0, "seq_no": 99999
    })
    assert res.status_code == 401
    assert "invalid device key" in res.get_json().get("error", "")


def test_future_timestamp_rejected(client):
    future_time = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    res = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": "ESP32-RICE-01", "weight_kg": 10.0, "seq_no": 90001, "measured_at": future_time
    })
    assert res.status_code == 422
    assert "future" in res.get_json().get("error", "")


def test_duplicate_telemetry_idempotency(client):
    seq = 95001
    # First reading
    res1 = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": "ESP32-RICE-01", "weight_kg": 12.0, "seq_no": seq
    })
    assert res1.status_code in [200, 201]

    # Duplicate reading
    res2 = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": "ESP32-RICE-01", "weight_kg": 12.0, "seq_no": seq
    })
    assert res2.status_code == 200
    assert res2.get_json()["status"] == "duplicate"
    assert res2.get_json()["seq_no"] == seq


def test_offline_telemetry_replay_accepted(client):
    # Delayed reading from hours ago (offline queue drained after Wi-Fi reconnect)
    past_time = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    seq = 96001
    res = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": "ESP32-RICE-01", "weight_kg": 11.5, "seq_no": seq, "measured_at": past_time
    })
    assert res.status_code in [200, 201]


def test_session_id_collision_resistance():
    # Rapidly open 10 sessions and assert all have unique session IDs
    barcode = "8901000000035"  # Basmati Rice
    session_ids = set()
    for _ in range(5):
        # Cancel pre-existing open session
        dev = db.query("SELECT session_id FROM refill_sessions WHERE device_id='ESP32-RICE-01' AND status='OPEN'")
        if dev:
            iot.cancel_session(dev[0]["session_id"], "test")

        code, body = iot.open_session(barcode, "test_user")
        assert code == 201
        sid = body["session_id"]
        assert sid not in session_ids
        session_ids.add(sid)
        iot.cancel_session(sid, "test_user")


def test_refill_requires_fresh_reading_after_session_start(client, login):
    barcode = "8901000000035"

    # Cancel pre-existing open session
    dev = db.query("SELECT session_id FROM refill_sessions WHERE device_id='ESP32-RICE-01' AND status='OPEN'")
    if dev:
        client.post(f"/api/refill/{dev[0]['session_id']}/cancel", headers=login("staff"))

    # 1. Open session
    open_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res.status_code == 201
    sid = open_res.get_json()["session_id"]

    # 2. Immediately attempt to complete WITHOUT a fresh reading after started_at
    # Must fail with 409 WAITING_FOR_READING
    comp_res = client.post(f"/api/refill/{sid}/complete", headers=login("staff"))
    assert comp_res.status_code == 409
    assert "fresh stable reading" in comp_res.get_json().get("error", "")

    # Cleanup
    client.post(f"/api/refill/{sid}/cancel", headers=login("staff"))


def test_refill_lifecycle_complete_and_idempotency(client, login):
    barcode = "8901000000035"
    dev_id = "ESP32-RICE-01"

    # Cancel pre-existing open session
    dev = db.query("SELECT session_id FROM refill_sessions WHERE device_id='ESP32-RICE-01' AND status='OPEN'")
    if dev:
        client.post(f"/api/refill/{dev[0]['session_id']}/cancel", headers=login("staff"))

    # 1. Open session
    open_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res.status_code == 201
    session = open_res.get_json()
    sid = session["session_id"]
    base_w = session["weight_before_kg"]

    # 2. Post fresh reading strictly after started_at with +2.5 kg weight increase
    time.sleep(1.05)
    fresh_time = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    seq = int(time.time() * 10) % 1000000
    res_ingest = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": dev_id, "weight_kg": round(base_w + 2.5, 2), "seq_no": seq, "stable": 1,
        "measured_at": fresh_time
    })
    assert res_ingest.status_code in [200, 201]

    # 3. Complete session -> 200 COMPLETED
    comp_res = client.post(f"/api/refill/{sid}/complete", headers=login("staff"))
    assert comp_res.status_code == 200
    assert comp_res.get_json()["status"] == "COMPLETED"
    assert comp_res.get_json()["refill_kg"] >= 0.2

    # 4. Idempotent re-completion -> returns 200 with duplicate=True
    comp_dup = client.post(f"/api/refill/{sid}/complete", headers=login("staff"))
    assert comp_dup.status_code == 200
    assert comp_dup.get_json()["duplicate"] is True
    assert comp_dup.get_json()["status"] == "COMPLETED"


def test_refill_zero_weight_rejected(client, login):
    barcode = "8901000000035"
    dev_id = "ESP32-RICE-01"

    # Cancel pre-existing open session
    dev = db.query("SELECT session_id FROM refill_sessions WHERE device_id='ESP32-RICE-01' AND status='OPEN'")
    if dev:
        client.post(f"/api/refill/{dev[0]['session_id']}/cancel", headers=login("staff"))

    # 1. Open session
    open_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res.status_code == 201
    sid = open_res.get_json()["session_id"]
    base_w = open_res.get_json()["weight_before_kg"]

    # 2. Post fresh reading with NO weight increase (delta = 0)
    time.sleep(1.05)
    fresh_time = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    seq = int(time.time() * 10 + 5) % 1000000
    client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": dev_id, "weight_kg": base_w, "seq_no": seq, "stable": 1,
        "measured_at": fresh_time
    })

    # 3. Complete must fail with 422 REJECTED
    comp_res = client.post(f"/api/refill/{sid}/complete", headers=login("staff"))
    assert comp_res.status_code == 422
    assert "no valid refill detected" in comp_res.get_json().get("error", "")


def test_delayed_offline_packet_watermark_and_distinct_timestamps(client):
    """
    Validates IoT sequence watermark and temporal separation:
    1. Higher sequence advances watermark.
    2. Lower sequence from delayed offline replay is accepted and stored.
    3. Monotonic device sequence watermark does not regress.
    4. Measurement timestamp (ts) and server arrival timestamp (ingested_at) are distinct.
    5. Duplicate packet with same (device_id, ts, seq_no) is ignored.
    """
    dev_id = "ESP32-RICE-01"

    # Step 1: Send reading with high sequence 98500
    t_now = datetime.now()
    res1 = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": dev_id, "weight_kg": 15.0, "seq_no": 98500,
        "measured_at": t_now.strftime("%Y-%m-%d %H:%M:%S")
    })
    assert res1.status_code in [200, 201]

    dev_after1 = db.query("SELECT last_seq FROM devices WHERE device_id=?", (dev_id,))[0]
    assert dev_after1["last_seq"] >= 98500
    watermark_before = dev_after1["last_seq"]

    # Step 2: Send delayed offline packet from 2 hours ago with lower sequence 98200
    t_delayed = (t_now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    res2 = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": dev_id, "weight_kg": 14.8, "seq_no": 98200,
        "measured_at": t_delayed
    })
    # Delayed offline replay must be accepted, not rejected or quarantined
    assert res2.status_code in [200, 201]

    # Step 3: Device sequence watermark must NOT regress to 98200
    dev_after2 = db.query("SELECT last_seq FROM devices WHERE device_id=?", (dev_id,))[0]
    assert dev_after2["last_seq"] == watermark_before

    # Step 4: Verify distinct ts vs ingested_at in iot_readings
    row = db.query("SELECT ts, ingested_at FROM iot_readings WHERE device_id=? AND seq_no=98200", (dev_id,))
    assert len(row) == 1
    assert row[0]["ts"] == t_delayed
    assert row[0]["ingested_at"] is not None
    assert row[0]["ingested_at"] != t_delayed  # Server time is current, not 2 hours ago

    # Step 5: Duplicate packet resubmission must be detected and return duplicate=True
    res_dup = client.post("/api/iot/readings", headers={"X-Device-Key": "rice-key-123"}, json={
        "device_id": dev_id, "weight_kg": 14.8, "seq_no": 98200,
        "measured_at": t_delayed
    })
    assert res_dup.status_code == 200
    assert res_dup.get_json()["status"] == "duplicate"

"""Calendar effects for a Tamil Nadu non-veg restaurant (extend as needed)."""
PURATTASI = [("2025-09-17", "2025-10-16"), ("2026-09-17", "2026-10-17"), ("2027-09-18", "2027-10-17")]
FESTIVALS = {
    "2025-08-15": "Independence Day", "2025-10-20": "Deepavali", "2025-12-31": "New Year's Eve",
    "2026-01-15": "Pongal", "2026-01-16": "Mattu Pongal", "2026-03-21": "Ramzan", "2026-05-27": "Bakrid",
    "2026-08-15": "Independence Day", "2026-11-08": "Deepavali", "2026-12-31": "New Year's Eve",
    "2027-01-15": "Pongal", "2027-01-16": "Mattu Pongal",
}


def is_purattasi(day_str):
    return int(any(a <= day_str <= b for a, b in PURATTASI))


def festival_name(day_str):
    return FESTIVALS.get(day_str)

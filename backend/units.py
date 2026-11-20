"""
SmartStock AI — Inventory Unit Conversion Engine.
Handles explicit, validated unit conversions for compatible mass and volume units.
Enforces that incompatible conversions (e.g. volume to mass without density) or unknown units are rejected.
"""

MASS_FACTORS = {
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
}

VOLUME_FACTORS = {
    "l": 1.0,
    "liter": 1.0,
    "liters": 1.0,
    "litre": 1.0,
    "litres": 1.0,
    "ml": 0.001,
    "milliliter": 0.001,
    "milliliters": 0.001,
    "millilitre": 0.001,
    "millilitres": 0.001,
}

CANONICAL_UNITS = {
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "g": "g", "gram": "g", "grams": "g",
    "l": "L", "liter": "L", "liters": "L", "litre": "L", "litres": "L",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml"
}


def normalize_unit_str(unit: str) -> str:
    if not unit or not isinstance(unit, str):
        raise ValueError("Unit must be a non-empty string")
    return unit.strip().lower()


def is_compatible_unit(from_unit: str, to_unit: str) -> bool:
    u1 = normalize_unit_str(from_unit)
    u2 = normalize_unit_str(to_unit)
    if u1 in MASS_FACTORS and u2 in MASS_FACTORS:
        return True
    if u1 in VOLUME_FACTORS and u2 in VOLUME_FACTORS:
        return True
    return False


def convert_quantity(qty: float, from_unit: str, to_unit: str) -> float:
    """
    Converts quantity from `from_unit` to `to_unit`.
    Returns rounded float (up to 4 decimal places for kitchen accuracy).
    Raises ValueError on unknown or incompatible units, or negative quantity.
    """
    if qty < 0:
        raise ValueError(f"Quantity cannot be negative (got {qty})")

    u_from = normalize_unit_str(from_unit)
    u_to = normalize_unit_str(to_unit)

    if u_from == u_to:
        return round(float(qty), 4)

    if u_from in MASS_FACTORS and u_to in MASS_FACTORS:
        qty_base_kg = float(qty) * MASS_FACTORS[u_from]
        res = qty_base_kg / MASS_FACTORS[u_to]
        return round(res, 4)
    elif u_from in VOLUME_FACTORS and u_to in VOLUME_FACTORS:
        qty_base_l = float(qty) * VOLUME_FACTORS[u_from]
        res = qty_base_l / VOLUME_FACTORS[u_to]
        return round(res, 4)
    else:
        raise ValueError(
            f"Incompatible or unsupported unit conversion: '{from_unit}' to '{to_unit}'. "
            f"Direct mass-to-volume conversions without validated density are strictly prohibited."
        )

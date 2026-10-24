"""Rescale saved snapshots without changing IDs, provenance or missing values."""
from copy import deepcopy
import math


def _positive(value):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or value <= 0):
        raise ValueError("Enter a positive, finite amount.")
    return float(value)


def rescale_food(entry, new_quantity):
    ratio = _positive(new_quantity) / _positive(entry["Qty"])
    updated = deepcopy(entry)
    updated["Qty"] = float(new_quantity)
    for key in ("Calories", "Protein", "Carbs", "Fat"):
        value = entry[key]
        if value is None:
            if key == "Calories":
                raise ValueError("Energy is missing; this entry cannot be rescaled.")
            updated[key] = None
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError("The stored nutrient value is invalid.")
        else:
            updated[key] = round(value * ratio, 6)
    return updated


def rescale_exercise(entry, new_minutes):
    ratio = _positive(new_minutes) / _positive(entry["Duration"])
    updated = deepcopy(entry)
    calories = entry["Calories Burned"]
    if not isinstance(calories, (int, float)) or isinstance(calories, bool) or not math.isfinite(calories) or calories < 0:
        raise ValueError("The stored exercise energy is invalid.")
    updated["Duration"] = float(new_minutes)
    updated["Calories Burned"] = round(calories * ratio, 6)
    return updated


def nutrient_coverage(entries, key):
    total, missing = 0.0, 0
    for entry in entries:
        value = entry.get(key)
        if value is None:
            missing += 1
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            total += value
        else:
            raise ValueError("A stored nutrient value is invalid.")
    return {"known_total": total, "missing_entries": missing,
            "entry_count": len(entries), "complete": missing == 0}

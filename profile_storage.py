"""Validated student profiles stored separately from daily food records."""
from datetime import datetime, timezone
import math

HEADERS = ["username", "height_cm", "weight_kg", "activity", "updated_at"]
ACTIVITIES = ["Sedentary (x25)", "Active (x30)"]


def validate_profile(height_cm, weight_kg, activity):
    try:
        height, weight = float(height_cm), float(weight_kg)
    except (TypeError, ValueError) as exc:
        raise ValueError("Height and weight must be numbers.") from exc
    if not math.isfinite(height) or not 100 <= height <= 200:
        raise ValueError("Height must be between 100 and 200 cm.")
    if not math.isfinite(weight) or not 30 <= weight <= 200:
        raise ValueError("Weight must be between 30 and 200 kg.")
    if activity not in ACTIVITIES:
        raise ValueError("Select a supported activity level.")
    return {"height_cm": height, "weight_kg": weight, "activity": activity}


def _read(sheet):
    if sheet is None:
        return []
    rows = sheet.get_all_values()
    # gspread represents a completely blank worksheet as [[]], not always [].
    # Only treat the sheet as empty when every cell is empty, so existing data
    # below a missing header is never mistaken for an unused worksheet.
    if not any(any(cell != "" for cell in row) for row in rows):
        return []
    if rows and rows[0] != HEADERS:
        raise ValueError("Unexpected profile columns. Existing data has not been changed.")
    return rows


def load_profile(sheet, username):
    rows = _read(sheet)
    matches = [row for row in rows[1:] if row and row[0] == username]
    if not matches:
        return None
    row = matches[-1]
    if len(row) < 4:
        raise ValueError("Saved profile is incomplete.")
    return validate_profile(row[1], row[2], row[3])


def save_profile(sheet, username, height_cm, weight_kg, activity):
    profile = validate_profile(height_cm, weight_kg, activity)
    if not isinstance(username, str) or not username.strip():
        raise ValueError("A signed-in account is required.")
    if sheet is None:
        raise ValueError("Profile storage is unavailable.")
    rows = _read(sheet)
    matches = [i + 1 for i, row in enumerate(rows[1:], start=1)
               if row and row[0] == username]
    output = [username, profile["height_cm"], profile["weight_kg"],
              profile["activity"], datetime.now(timezone.utc).isoformat(timespec="seconds")]
    if not rows:
        sheet.update(range_name="A1", values=[HEADERS], value_input_option="RAW")
    if matches:
        sheet.update(range_name=f"A{matches[-1]}", values=[output], value_input_option="RAW")
    else:
        sheet.append_row(output, value_input_option="RAW")
    return profile

"""Read and update dated summaries without changing the original five columns."""
import json
import math

HEADERS = ["Date", "Food_Log", "Exercise_Log", "Net_Calories", "username"]
DETAIL_HEADERS = ["Food_JSON", "Exercise_JSON"]


def _read(sheet):
    rows = sheet.get_all_values()
    if not any(any(cell != "" for cell in row) for row in rows):
        return HEADERS.copy(), []
    if rows[0][:5] != HEADERS or len(set(rows[0])) != len(rows[0]):
        raise ValueError("Unexpected sheet headers. No records were changed.")
    return rows[0], rows[1:]


def _matches(rows, username, day):
    return [(index + 2, row) for index, row in enumerate(rows)
            if len(row) >= 5 and row[0] == str(day) and row[4] == username]


def _decode(value, kind):
    items = json.loads(value)
    required = ({"Meal", "Food", "Qty", "Calories", "Protein", "Carbs", "Fat"}
                if kind == "food" else {"Activity", "Duration", "Calories Burned"})
    numeric = required - {"Meal", "Food", "Activity"}
    if not isinstance(items, list):
        raise ValueError("Saved details are invalid; no records were changed.")
    for item in items:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("Saved details are incomplete; no records were changed.")
        for key in numeric:
            value = item[key]
            if kind == "food" and key in {"Protein", "Carbs", "Fat"} and value is None:
                continue
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) or value < 0):
                raise ValueError("Saved amounts are invalid; no records were changed.")
    return items


def load_day(sheet, username, day):
    headers, rows = _read(sheet)
    matches = _matches(rows, username, day)
    if not matches:
        return {"food_log": [], "exercise_log": [], "legacy": False}
    _, row = matches[-1]
    details = dict(zip(headers, row))
    if not all(details.get(key) for key in DETAIL_HEADERS):
        return {"food_log": [], "exercise_log": [], "legacy": True,
                "summary": {key: details.get(key, "") for key in HEADERS[:4]}}
    return {"food_log": _decode(details["Food_JSON"], "food"),
            "exercise_log": _decode(details["Exercise_JSON"], "exercise"),
            "legacy": False}


def save_day(sheet, username, day, foods, exercises, net_calories,
             food_summary, exercise_summary, replace_legacy=False):
    # Serialize and validate before any write.
    food_json = json.dumps(foods, ensure_ascii=False, allow_nan=False)
    exercise_json = json.dumps(exercises, ensure_ascii=False, allow_nan=False)
    _decode(food_json, "food")
    _decode(exercise_json, "exercise")
    headers, rows = _read(sheet)
    matches = _matches(rows, username, day)
    if matches:
        previous = dict(zip(headers, matches[-1][1]))
        if not all(previous.get(key) for key in DETAIL_HEADERS) and not replace_legacy:
            raise ValueError("This date has an older summary. Confirm replacement first.")
    new_headers = headers + [key for key in DETAIL_HEADERS if key not in headers]
    if new_headers != headers:
        sheet.update(range_name="A1", values=[new_headers], value_input_option="RAW")
    values = {"Date": str(day), "Food_Log": food_summary,
              "Exercise_Log": exercise_summary, "Net_Calories": net_calories,
              "username": username, "Food_JSON": food_json, "Exercise_JSON": exercise_json}
    previous_row = matches[-1][1] if matches else []
    output = [values.get(key, previous_row[i] if i < len(previous_row) else "")
              for i, key in enumerate(new_headers)]
    if matches:
        sheet.update(range_name=f"A{matches[-1][0]}", values=[output], value_input_option="RAW")
        return "updated"
    sheet.append_row(output, value_input_option="RAW")
    return "created"

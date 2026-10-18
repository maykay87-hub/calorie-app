"""Export only records already scoped to the current signed-in account."""
import csv
import io
import json
from tracker_storage import _decode


def _text(value):
    text = "" if value is None else str(value)
    # Keep CSV text inert when opened in spreadsheet software; numbers retain
    # their numeric type in the caller and are not altered by this function.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_history_csv(records):
    output = io.StringIO(newline="")
    fields = ["Date", "Net_Calories_kcal", "Protein_complete_g", "Protein_known_g",
              "Protein_missing_entries", "Food_entries", "Status", "Food_Log", "Exercise_Log"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in records:
        writer.writerow({"Date": _text(item["Date"]), "Net_Calories_kcal": item["Net_Calories"],
                         "Protein_complete_g": item["Protein"], "Protein_known_g": item["known_protein"],
                         "Protein_missing_entries": item["missing_protein_entries"], "Food_entries": item["food_entries"],
                         "Status": item["status"], "Food_Log": _text(item["Food_Log"]),
                         "Exercise_Log": _text(item["Exercise_Log"])})
    return output.getvalue().encode("utf-8-sig")


def export_draft(username, day, foods, exercises):
    food_json = json.dumps(foods, ensure_ascii=False, allow_nan=False)
    exercise_json = json.dumps(exercises, ensure_ascii=False, allow_nan=False)
    _decode(food_json, "food")
    _decode(exercise_json, "exercise")
    return json.dumps({"schema_version": 1, "username": username, "date": str(day),
                       "food_log": foods, "exercise_log": exercises},
                      ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")

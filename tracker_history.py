"""Saved-history views use the same latest-row rule as the day editor."""
from datetime import date
import math
from entry_editor import nutrient_coverage
from tracker_storage import _read, _decode


def load_history(sheet, username):
    headers, rows = _read(sheet)
    latest = {}
    for row in rows:
        values = dict(zip(headers, row))
        if values.get("username") != username or not values.get("Date"):
            continue
        day = str(values["Date"])
        try:
            date.fromisoformat(day)
        except ValueError:
            # Do not put an invalid date onto a time-series chart.
            continue
        try:
            net = float(values.get("Net_Calories", ""))
            if not math.isfinite(net):
                net = None
        except (TypeError, ValueError):
            net = None
        item = {"Date": day, "Net_Calories": net,
                "Food_Log": values.get("Food_Log", ""),
                "Exercise_Log": values.get("Exercise_Log", ""),
                "Protein": None, "known_protein": None,
                "missing_protein_entries": None, "food_entries": None,
                "status": "legacy"}
        if values.get("Food_JSON") and values.get("Exercise_JSON"):
            try:
                foods = _decode(values["Food_JSON"], "food")
                _decode(values["Exercise_JSON"], "exercise")
                protein = nutrient_coverage(foods, "Protein")
                item.update(known_protein=protein["known_total"],
                            missing_protein_entries=protein["missing_entries"],
                            food_entries=protein["entry_count"], status="detailed")
                if protein["complete"]:
                    item["Protein"] = protein["known_total"]
            except (ValueError, TypeError):
                item["status"] = "invalid_details"
        latest[day] = item
    return [latest[day] for day in sorted(latest, reverse=True)]

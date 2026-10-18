"""Local source-backed food references and explicit missing-nutrient handling."""
import json
import math
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "data" / "foods_kkm.json").read_text())
SOURCE = _DATA["source"]
REFERENCE_RECORDS = {record["id"]: record for record in _DATA["records"]}

# Keep these IDs and their saved entries readable, but avoid offering their
# ambiguous/zero-energy records for new logging when better entries exist.
HIDDEN_LEGACY_IDS = {
    "Ulam (Cucumber/Raw Greens)",
    "Sawi / Choy Sum (Blanched)",
    "Steamed Broccoli/ cauliflower",
    "Nasi Lemak (Standard Hawker)",
    "Chicken Rice (Roasted - 1 plate)",
    "Tosai (1 piece)",
    "Teh Tarik (1 glass)",
}


def reference_database():
    return {key: {"Cals": item["energy_kcal"], "Prot": item["protein_g"],
                  "Carbs": item["carbs_g"], "Fat": item["fat_g"]}
            for key, item in REFERENCE_RECORDS.items()}


def format_energy(value):
    """Keep half-serving energy visible instead of truncating it to an integer."""
    return f"{float(value):,.1f}".rstrip("0").rstrip(".")


def make_food_entry(database, food_id, meal, quantity):
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not math.isfinite(quantity) or quantity <= 0:
        raise ValueError("Serving quantity must be positive and finite.")
    nutrients = database[food_id]
    entry = {"Meal": meal, "Food": food_id, "Qty": quantity}
    for source_key, target_key in [("Cals", "Calories"), ("Prot", "Protein"),
                                   ("Carbs", "Carbs"), ("Fat", "Fat")]:
        value = nutrients[source_key]
        entry[target_key] = None if value is None else value * quantity
    reference = REFERENCE_RECORDS.get(food_id)
    if reference:
        entry["Source"] = {
            "status": "published_energy_reference", "title": SOURCE["title"],
            "url": SOURCE["url"], "pdf_page": reference["pdf_page"],
            "original_name": reference["original_name"],
            "reference_code": reference["reference_code"],
            "weight_g_per_serving": reference["weight_g"],
        }
    else:
        entry["Source"] = {"status": "legacy_estimate", "title": "Original exchange estimate; source not recorded"}
    return entry

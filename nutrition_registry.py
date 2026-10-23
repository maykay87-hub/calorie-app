"""Local source-backed food references and explicit missing-nutrient handling."""
from copy import deepcopy
import json
import math
from pathlib import Path
from exchange_foods import EXCHANGE_RECORDS, EXCHANGE_SOURCE, RESTORED_EXCHANGE_IDS

_DATA = json.loads((Path(__file__).parent / "data" / "foods_kkm.json").read_text())
SOURCE = _DATA["source"]
REFERENCE_RECORDS = {record["id"]: record for record in _DATA["records"]}
_SG_DATA = json.loads((Path(__file__).parent / "data" / "foods_hpb_sg.json").read_text())
SG_SOURCE = _SG_DATA["source"]
REFERENCE_RECORDS.update({record["id"]: record for record in _SG_DATA["records"]})

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
HIDDEN_LEGACY_IDS.update(key for record in _SG_DATA["records"] for key in record.get("replaces", [])
                         if key not in RESTORED_EXCHANGE_IDS)


def reference_database():
    return {key: {"Cals": item["energy_kcal"], "Prot": item["protein_g"],
                  "Carbs": item["carbs_g"], "Fat": item["fat_g"]}
            for key, item in REFERENCE_RECORDS.items()}


def reference_portion(item):
    """Preserve published volume units; never treat ml as grams."""
    return item.get("portion_amount", item["weight_g"]), item.get("portion_unit", "g")


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
    exchange = EXCHANGE_RECORDS.get(food_id)
    if exchange:
        entry['Source'] = dict(EXCHANGE_SOURCE, status='food_exchange_estimate',
            pdf_page=exchange['pdf_page'], basis=exchange['basis'],
            weight_g_per_serving=exchange['weight_g'])
        return entry
    reference = REFERENCE_RECORDS.get(food_id)
    if reference:
        if reference.get("source_id") == "hpb_sgfoodid":
            amount, unit = reference_portion(reference)
            entry["Source"] = {
                "status": "published_nutrition_reference", "title": SG_SOURCE["title"],
                "url": reference["source_url"], "food_code": reference["food_code"],
                "region": "Singapore", "data_year": reference["data_year"],
                "method": reference["method"], "original_name": reference["original_name"],
                "weight_g_per_serving": reference["weight_g"],
                "edible_portion_percent": reference["edible_portion_percent"],
                "amount_per_serving": amount, "portion_unit": unit,
                "portion_basis": reference.get("portion_basis", "published_default_portion"),
            }
            if reference.get("provider_default_portion"):
                entry["Source"]["provider_default_portion"] = reference["provider_default_portion"]
                entry["Source"]["provider_edible_portion_percent"] = reference["provider_edible_portion_percent"]
            basis = "per_100ml" if unit == "ml" else "per_100g"
            entry["Source"][basis] = deepcopy(reference[basis])
            return entry
        entry["Source"] = {
            "status": "published_energy_reference", "title": SOURCE["title"],
            "url": SOURCE["url"], "pdf_page": reference["pdf_page"],
            "original_name": reference["original_name"],
            "reference_code": reference["reference_code"],
            "weight_g_per_serving": reference["weight_g"],
        }
        if reference.get("macronutrient_source"):
            entry["Source"]["macronutrients"] = deepcopy(reference["macronutrient_source"])
    else:
        entry["Source"] = {"status": "legacy_estimate", "title": "Original exchange estimate; source not recorded"}
    return entry

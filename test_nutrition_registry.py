import copy
import json
import math
import unittest
from nutrition_registry import (SOURCE, REFERENCE_RECORDS, HIDDEN_LEGACY_IDS,
                                 reference_database, make_food_entry, format_energy)
from food_catalogue import filter_foods, food_label
from tracker_storage import load_day, save_day, HEADERS
from test_tracker_storage import Sheet


class ReferenceFoodTests(unittest.TestCase):
    def setUp(self):
        self.database = reference_database()

    def test_reference_manifest_has_traceable_portions_and_explicit_missing_macros(self):
        self.assertEqual(len(REFERENCE_RECORDS), 65)
        for key, item in REFERENCE_RECORDS.items():
            with self.subTest(food=key):
                self.assertGreater(item["weight_g"], 0)
                self.assertGreater(item["energy_kcal"], 0)
                self.assertTrue(math.isfinite(item["energy_kcal"]))
                if item.get("source_id") != "hpb_sgfoodid":
                    self.assertTrue(1 <= item["pdf_page"] <= 108)
                    self.assertIn(item["reference_code"], SOURCE["reference_codes"])
                self.assertTrue(item["original_name"])
                for nutrient in ["Prot", "Carbs", "Fat"]:
                    if item.get("macronutrient_source") or item.get("source_id") == "hpb_sgfoodid":
                        self.assertGreaterEqual(self.database[key][nutrient], 0)
                    else:
                        self.assertIsNone(self.database[key][nutrient])

    def test_matched_macros_are_scaled_and_source_is_saved(self):
        matched = [x for x in REFERENCE_RECORDS.values() if x.get("macronutrient_source")]
        self.assertEqual(len(matched), 6)
        for item in matched:
            source = item["macronutrient_source"]
            raw = source["per_100g"]
            self.assertLess(abs(raw["Energy"] * item["weight_g"] / 100 - item["energy_kcal"]) / item["energy_kcal"], .025)
            entry = make_food_entry(self.database, item["id"], "Lunch", .5)
            self.assertAlmostEqual(entry["Protein"], round(raw["Protein"] * item["weight_g"] / 100, 3) * .5)
            self.assertEqual(entry["Source"]["macronutrients"]["food_code"], source["food_code"])
            entry["Source"]["macronutrients"]["title"] = "changed"
            self.assertEqual(source["title"], "MyFCD 1997")

    def test_soup_and_dry_noodles_are_distinct_portion_specific_records(self):
        wantan = filter_foods(self.database, query="云吞面")
        pan = filter_foods(self.database, query="板面")
        self.assertEqual(len(wantan), 2)
        self.assertEqual(len(pan), 3)
        self.assertEqual(sorted(self.database[key]["Cals"] for key in wantan), [625, 631])
        self.assertEqual(sorted(self.database[key]["Cals"] for key in pan), [602, 655, 678])
        self.assertEqual(len(filter_foods(self.database, query="chilli pan mee")), 1)

    def test_sg_complete_meals_keep_nutrients_portion_and_region_together(self):
        records = [x for x in REFERENCE_RECORDS.values() if x.get("source_id") == "hpb_sgfoodid"]
        self.assertEqual(len(records), 19)
        for item in records:
            with self.subTest(food=item["food_code"]):
                edible = item["weight_g"] * item["edible_portion_percent"] / 100
                for raw_key, key in [("energy", "energy_kcal"), ("protein", "protein_g"), ("carbohydrate", "carbs_g"), ("fat", "fat_g")]:
                    tolerance = .5 * edible / 100 + .5 if raw_key == "energy" else .005 * edible / 100 + .005
                    self.assertLessEqual(abs(item["per_100g"][raw_key] * edible / 100 - item[key]), tolerance)
                entry = make_food_entry(self.database, item["id"], "Lunch", .5)
                self.assertEqual(entry["Protein"], item["protein_g"] / 2)
                self.assertEqual(entry["Source"]["region"], "Singapore")
                self.assertEqual(entry["Source"]["food_code"], item["food_code"])
                self.assertIn("SG参考", food_label(item["id"]))
                self.assertIn(item["method"], ["Lab Analysis", "Derived"])
                for previous in item["replaces"]:
                    self.assertIn(previous, HIDDEN_LEGACY_IDS)
                    self.assertNotIn(previous, filter_foods(dict(self.database, **{previous: {}})))

    def test_half_portion_scales_energy_and_preserves_unknown_macros_and_source(self):
        key = "Wantan Mee Dry (1 plate, 330 g; KKM reference)"
        entry = make_food_entry(self.database, key, "Lunch", 0.5)
        self.assertEqual(entry["Calories"], 220)
        self.assertIsNone(entry["Protein"])
        self.assertIsNone(entry["Carbs"])
        self.assertIsNone(entry["Fat"])
        self.assertEqual(entry["Source"]["weight_g_per_serving"], 330)
        self.assertEqual(entry["Source"]["pdf_page"], 61)

    def test_reference_entry_saves_and_restores_without_losing_unknowns_or_source(self):
        key = "Pan Mee Soup (1 bowl, 528 g; KKM reference)"
        entry = make_food_entry(self.database, key, "Lunch", 1)
        sheet = Sheet([HEADERS])
        save_day(sheet, "student", "2026-10-18", [entry], [], 475, food_label(key), "None")
        restored = load_day(sheet, "student", "2026-10-18")
        self.assertEqual(restored["food_log"], [entry])
        self.assertIsNone(restored["food_log"][0]["Protein"])

    def test_missing_energy_is_rejected_instead_of_saved_as_zero(self):
        key = next(iter(self.database))
        entry = make_food_entry(self.database, key, "Lunch", 1)
        entry["Calories"] = None
        with self.assertRaises(ValueError):
            save_day(Sheet([HEADERS]), "student", "2026-10-18", [entry], [], 0, "", "")

    def test_invalid_quantities_do_not_produce_entries(self):
        key = next(iter(self.database))
        for value in [0, -1, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                make_food_entry(self.database, key, "Lunch", value)

    def test_energy_display_preserves_half_calories_and_whole_values(self):
        self.assertEqual(format_energy(237.5), "237.5")
        self.assertEqual(format_energy(1000), "1,000")
        self.assertEqual(format_energy(0), "0")

    def test_hidden_legacy_ids_remain_readable_but_cannot_be_selected(self):
        legacy = "Nasi Lemak (Standard Hawker)"
        database = dict(self.database, **{legacy: {"Cals": 440, "Prot": 11, "Carbs": 30, "Fat": 25}})
        self.assertIn(legacy, HIDDEN_LEGACY_IDS)
        self.assertNotIn(legacy, filter_foods(database, query="nasi lemak"))
        old = {"Meal": "Lunch", "Food": legacy, "Qty": 1, "Calories": 440,
               "Protein": 11, "Carbs": 30, "Fat": 25}
        sheet = Sheet([HEADERS])
        save_day(sheet, "student", "2026-10-17", [old], [], 440, "old", "None")
        self.assertEqual(load_day(sheet, "student", "2026-10-17")["food_log"], [old])


if __name__ == "__main__":
    unittest.main()

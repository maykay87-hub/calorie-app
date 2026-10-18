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
        self.assertEqual(len(REFERENCE_RECORDS), 46)
        for key, item in REFERENCE_RECORDS.items():
            with self.subTest(food=key):
                self.assertGreater(item["weight_g"], 0)
                self.assertGreater(item["energy_kcal"], 0)
                self.assertTrue(math.isfinite(item["energy_kcal"]))
                self.assertTrue(1 <= item["pdf_page"] <= 108)
                self.assertIn(item["reference_code"], SOURCE["reference_codes"])
                self.assertTrue(item["original_name"])
                self.assertIsNone(self.database[key]["Prot"])
                self.assertIsNone(self.database[key]["Carbs"])
                self.assertIsNone(self.database[key]["Fat"])

    def test_soup_and_dry_noodles_are_distinct_portion_specific_records(self):
        wantan = filter_foods(self.database, query="云吞面")
        pan = filter_foods(self.database, query="板面")
        self.assertEqual(len(wantan), 2)
        self.assertEqual(len(pan), 2)
        self.assertEqual(sorted(self.database[key]["Cals"] for key in wantan), [300, 440])
        self.assertEqual(sorted(self.database[key]["Cals"] for key in pan), [315, 475])
        self.assertEqual(filter_foods(self.database, query="chilli pan mee"), [])

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

from copy import deepcopy
import unittest
from entry_editor import rescale_food, rescale_exercise, nutrient_coverage
from nutrition_registry import reference_database, make_food_entry
from tracker_storage import save_day, load_day, HEADERS
from test_tracker_storage import Sheet, FOOD


class EntryEditorTests(unittest.TestCase):
    def test_food_edit_scales_all_known_nutrients_without_mutating_original(self):
        before = deepcopy(FOOD)
        updated = rescale_food(FOOD, 2)
        self.assertEqual(updated["Calories"], 150)
        self.assertEqual(updated["Protein"], 4)
        self.assertEqual(FOOD, before)

    def test_reference_edit_preserves_unknown_macros_and_source(self):
        database = reference_database()
        key = next(iter(database))
        entry = make_food_entry(database, key, "Lunch", 1)
        updated = rescale_food(entry, 0.5)
        self.assertEqual(updated["Calories"], entry["Calories"] / 2)
        self.assertIsNone(updated["Protein"])
        self.assertEqual(updated["Source"], entry["Source"])
        updated["Source"]["title"] = "changed copy"
        self.assertNotEqual(updated["Source"], entry["Source"])

    def test_repeated_food_edits_use_current_snapshot_ratio(self):
        updated = rescale_food(rescale_food(FOOD, 2), 0.5)
        self.assertEqual(updated["Calories"], 37.5)
        self.assertEqual(updated["Protein"], 1)

    def test_exercise_edit_scales_duration_and_energy(self):
        original = {"Activity": "Yoga", "Duration": 30, "Calories Burned": 100}
        self.assertEqual(rescale_exercise(original, 45),
                         {"Activity": "Yoga", "Duration": 45.0, "Calories Burned": 150})
        self.assertEqual(original["Duration"], 30)

    def test_invalid_amounts_are_rejected(self):
        for value in [0, -1, True, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                rescale_food(FOOD, value)

    def test_nutrient_coverage_distinguishes_unknown_from_true_zero(self):
        self.assertEqual(nutrient_coverage([{"Protein": None}], "Protein"),
                         {"known_total": 0, "missing_entries": 1, "entry_count": 1, "complete": False})
        result = nutrient_coverage([{"Protein": 0}, {"Protein": 7}, {"Protein": None}], "Protein")
        self.assertEqual(result["known_total"], 7)
        self.assertEqual(result["missing_entries"], 1)

    def test_edit_and_individual_deletion_survive_save_and_reload(self):
        entries = [deepcopy(FOOD), deepcopy(FOOD)]
        entries[0] = rescale_food(entries[0], 2)
        entries.pop(1)
        sheet = Sheet([HEADERS])
        save_day(sheet, "student", "2026-10-18", entries, [], 150, "Rice", "None")
        self.assertEqual(load_day(sheet, "student", "2026-10-18")["food_log"], entries)


if __name__ == "__main__":
    unittest.main()

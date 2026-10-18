import unittest
from label_entry import make_label_entry, entry_amount_label
from entry_editor import rescale_food, nutrient_coverage
from tracker_storage import save_day, load_day, HEADERS
from test_tracker_storage import Sheet


class PackageLabelTests(unittest.TestCase):
    def test_per_100g_scales_to_amount_eaten(self):
        entry = make_label_entry("Wholemeal bread", "Breakfast", "g", 100, 30, 240, 10, 40, 4)
        self.assertEqual((entry["Qty"], entry["Calories"], entry["Protein"], entry["Carbs"], entry["Fat"]), (.3, 72, 3, 12, 1.2))
        self.assertEqual(entry_amount_label(entry), "30 g")

    def test_per_250ml_and_half_serving(self):
        entry = make_label_entry("Milk", "Snack", "ml", 250, 125, 150, 8)
        self.assertEqual(entry["Calories"], 75)
        self.assertEqual(entry["Protein"], 4)
        self.assertEqual(entry_amount_label(entry), "125 ml")
        half = make_label_entry("Yogurt", "Snack", "serving", 1, .5, 100, 6)
        self.assertEqual(half["Protein"], 3)
        self.assertEqual(entry_amount_label(half), "0.5 份")

    def test_unknown_stays_unknown_and_true_zero_is_valid(self):
        entry = make_label_entry("Drink", "Snack", "ml", 100, 250, 0, None, 0, None)
        self.assertEqual(entry["Calories"], 0)
        self.assertIsNone(entry["Protein"])
        self.assertEqual(entry["Carbs"], 0)
        self.assertEqual(nutrient_coverage([entry], "Protein")["missing_entries"], 1)

    def test_invalid_labels_are_rejected_before_logging(self):
        values = dict(name="Milk", meal="Breakfast", unit="ml", label_amount=100, consumed_amount=200, calories=50)
        for field, bad in [("name", " "), ("name", "x" * 121), ("meal", "unknown"),
                           ("unit", "oz"), ("calories", None), ("calories", -1),
                           ("protein", -2), ("label_amount", 0), ("consumed_amount", 0),
                           ("consumed_amount", float("inf")), ("fat", True)]:
            with self.subTest(field=field, bad=bad):
                with self.assertRaises(ValueError):
                    make_label_entry(**dict(values, **{field: bad}))

    def test_saved_label_is_editable_and_keeps_original_label_values(self):
        entry = make_label_entry("Milk", "Breakfast", "ml", 250, 125, 150, 8)
        edited = rescale_food(entry, 1)
        self.assertEqual(edited["Calories"], 150)
        self.assertEqual(edited["Source"]["nutrients_per_label_amount"]["Protein"], 8)
        sheet = Sheet([HEADERS])
        save_day(sheet, "student", "2026-10-18", [edited], [], 150, edited["Food"], "None")
        self.assertEqual(load_day(sheet, "student", "2026-10-18")["food_log"], [edited])

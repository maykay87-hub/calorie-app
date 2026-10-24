from copy import deepcopy
import unittest
from label_entry import make_label_entry
from label_library import as_template, remember_label, reuse_label, template_key, load_personal_labels
from tracker_storage import save_day, HEADERS
from test_tracker_storage import Sheet, FOOD


class PersonalLabelTests(unittest.TestCase):
    def label(self, name='Milk', calories=150):
        return make_label_entry(name, 'Snack', 'ml', 250, 125, calories, 8)

    def test_template_uses_original_label_basis_not_last_eaten_amount(self):
        entry = self.label()
        template = as_template(entry)
        self.assertEqual(template['Qty'], 1)
        self.assertEqual(template['Calories'], 150)
        reused = reuse_label(template, 'Dinner', 500)
        self.assertEqual(reused['Calories'], 300)
        self.assertEqual(reused['Protein'], 16)
        self.assertIsNone(reused['Carbs'])
        self.assertEqual(reused['Meal'], 'Dinner')
        self.assertEqual(entry['Calories'], 75)

    def test_same_product_basis_replaces_template_without_mutating_old_snapshot(self):
        old = self.label(' Brand Milk ', 150)
        before = deepcopy(old)
        library = remember_label([], old)
        updated = self.label('brand   milk', 160)
        library = remember_label(library, updated)
        self.assertEqual(len(library), 1)
        self.assertEqual(library[0]['Calories'], 160)
        self.assertEqual(old, before)

    def test_flavours_are_distinct_and_library_has_a_bound(self):
        library = []
        for i in range(35):
            library = remember_label(library, self.label(f'Product {i}'))
        self.assertEqual(len(library), 30)
        self.assertNotEqual(template_key(as_template(self.label('Milk chocolate'))),
                            template_key(as_template(self.label('Milk plain'))))

    def test_saved_labels_are_account_scoped_and_latest_consumption_date_wins(self):
        sheet = Sheet([HEADERS])
        save_day(sheet, 'alice', '2026-10-18', [self.label(calories=160)], [], 80, 'milk', 'None')
        save_day(sheet, 'alice', '2026-10-17', [self.label(calories=150)], [], 75, 'milk', 'None')
        save_day(sheet, 'bob', '2026-10-19', [self.label('Private brand')], [], 75, 'milk', 'None')
        result = load_personal_labels(sheet, 'alice')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['Calories'], 160)
        self.assertEqual(load_personal_labels(sheet, 'unknown'), [])

    def test_invalid_optional_template_does_not_block_other_labels(self):
        self.assertIsNone(as_template(FOOD))
        self.assertIsNone(as_template(dict(FOOD, Source={'status': 'user_entered_package_label'})))
        with self.assertRaises(ValueError):
            reuse_label(FOOD, 'Lunch', 100)

    def test_superseded_daily_rows_do_not_resurrect_deleted_label(self):
        sheet = Sheet([HEADERS])
        save_day(sheet, 'alice', '2026-10-18', [self.label()], [], 75, 'milk', 'None')
        sheet.rows.append(['2026-10-18', 'None', 'None', '0', 'alice', '[]', '[]'])
        self.assertEqual(load_personal_labels(sheet, 'alice'), [])

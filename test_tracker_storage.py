import copy
import unittest
from tracker_storage import HEADERS, load_day, save_day, SaveConflictError, day_snapshot

FOOD = {"Meal": "Breakfast", "Food": "Rice", "Qty": 1.0,
        "Calories": 75, "Protein": 2, "Carbs": 15, "Fat": 0}
EXERCISE = {"Activity": "Yoga", "Duration": 30, "Calories Burned": 100}


class Sheet:
    def __init__(self, rows=None):
        self.rows = copy.deepcopy(rows if rows is not None else [HEADERS])

    def get_all_values(self):
        return copy.deepcopy(self.rows)

    def update(self, range_name, values, value_input_option):
        index = int(range_name[1:]) - 1
        while len(self.rows) <= index:
            self.rows.append([])
        self.rows[index] = values[0][:]

    def append_row(self, values, value_input_option):
        self.rows.append(values[:])


class StorageTests(unittest.TestCase):
    def test_stale_page_cannot_overwrite_changed_saved_day(self):
        sheet = Sheet()
        baseline = load_day(sheet, 'alice', '2026-10-18')['baseline']
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75, 'rice', 'None', expected_snapshot=baseline)
        before = copy.deepcopy(sheet.rows)
        with self.assertRaises(SaveConflictError):
            save_day(sheet, 'alice', '2026-10-18', [], [], 0, 'None', 'None', expected_snapshot=baseline)
        self.assertEqual(sheet.rows, before)

    def test_lost_acknowledgement_retry_with_identical_content_is_idempotent(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75, 'rice', 'None', expected_snapshot=None)
        self.assertEqual(save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75.0, 'rice', 'None', expected_snapshot=None), 'unchanged')
        self.assertEqual(len(sheet.rows), 2)

    def test_loaded_baseline_survives_numeric_sheet_rendering_and_other_account_updates(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75, 'rice', 'None')
        baseline = load_day(sheet, 'alice', '2026-10-18')['baseline']
        sheet.rows[1][3] = '75.0'
        save_day(sheet, 'bob', '2026-10-18', [], [], 0, 'None', 'None')
        save_day(sheet, 'alice', '2026-10-18', [FOOD, FOOD], [], 150, 'rice twice', 'None', expected_snapshot=baseline)
        self.assertEqual(len(load_day(sheet, 'alice', '2026-10-18')['food_log']), 2)

    def test_baseline_ignores_floating_point_rendering_noise(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75.00000000000001, 'rice', 'None')
        baseline = load_day(sheet, 'alice', '2026-10-18')['baseline']
        sheet.rows[1][3] = '75'
        save_day(sheet, 'alice', '2026-10-18', [FOOD, FOOD], [], 150, 'rice twice', 'None', expected_snapshot=baseline)
        self.assertEqual(len(load_day(sheet, 'alice', '2026-10-18')['food_log']), 2)

    def test_stale_legacy_replacement_is_also_blocked(self):
        sheet = Sheet([HEADERS, ['2026-10-18', 'old', 'None', '75', 'alice']])
        baseline = load_day(sheet, 'alice', '2026-10-18')['baseline']
        sheet.rows[1][1] = 'changed elsewhere'
        with self.assertRaises(SaveConflictError):
            save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75, 'rice', 'None', replace_legacy=True, expected_snapshot=baseline)
        self.assertEqual(sheet.rows[1][1], 'changed elsewhere')

    def test_invalid_entry_metadata_and_zero_amounts_are_rejected_before_write(self):
        for change in [{"Food": []}, {"Meal": ""}, {"Qty": 0}]:
            sheet = Sheet()
            before = copy.deepcopy(sheet.rows)
            with self.assertRaises(ValueError):
                save_day(sheet, 'alice', '2026-10-18', [dict(FOOD, **change)], [], 75, '', '')
            self.assertEqual(sheet.rows, before)
        for net in [float('nan'), float('inf'), True, '75']:
            sheet = Sheet()
            with self.assertRaises(ValueError):
                save_day(sheet, 'alice', '2026-10-18', [FOOD], [], net, '', '')
            self.assertEqual(sheet.rows, [HEADERS])

    def save(self, sheet, user="alice", day="2026-10-18", foods=None, **kwargs):
        return save_day(sheet, user, day, [FOOD] if foods is None else foods,
                        [EXERCISE], -25, "Rice summary", "Yoga summary", **kwargs)

    def test_repeat_save_updates_one_row_and_roundtrips_after_new_session(self):
        sheet = Sheet()
        self.assertEqual(self.save(sheet), "created")
        self.assertEqual(self.save(sheet, foods=[FOOD, FOOD]), "updated")
        self.assertEqual(len(sheet.rows), 2)
        loaded = load_day(sheet, "alice", "2026-10-18")
        self.assertEqual(loaded["food_log"], [FOOD, FOOD])
        self.assertEqual(loaded["exercise_log"], [EXERCISE])

    def test_gspread_empty_sheet_shapes_allow_initial_daily_save(self):
        for rows in [[], [[]], [[""]], [["", ""], ["", ""]]]:
            with self.subTest(rows=rows):
                sheet = Sheet(rows)
                self.assertEqual(load_day(sheet, "alice", "2026-10-18")["food_log"], [])
                self.save(sheet)
                self.assertEqual(load_day(sheet, "alice", "2026-10-18")["food_log"], [FOOD])

    def test_users_and_dates_do_not_overwrite_each_other(self):
        sheet = Sheet()
        self.save(sheet)
        self.save(sheet, user="bob")
        self.save(sheet, day="2026-10-19")
        self.assertEqual(len(sheet.rows), 4)
        self.assertEqual(load_day(sheet, "charlie", "2026-10-18")["food_log"], [])

    def test_legacy_summary_preserved_without_confirmation(self):
        sheet = Sheet([HEADERS, ["2026-10-18", "old", "None", "75", "alice"]])
        before = copy.deepcopy(sheet.rows)
        self.assertTrue(load_day(sheet, "alice", "2026-10-18")["legacy"])
        with self.assertRaises(ValueError):
            self.save(sheet)
        self.assertEqual(sheet.rows, before)
        self.save(sheet, replace_legacy=True)
        self.assertFalse(load_day(sheet, "alice", "2026-10-18")["legacy"])
        self.assertEqual(len(sheet.rows), 2)

    def test_empty_saved_day_does_not_reload_removed_food(self):
        sheet = Sheet()
        self.save(sheet)
        self.save(sheet, foods=[])
        self.assertEqual(load_day(sheet, "alice", "2026-10-18")["food_log"], [])

    def test_existing_duplicates_are_preserved_and_latest_is_updated(self):
        sheet = Sheet([HEADERS, ["2026-10-18", "old1", "None", "75", "alice"],
                       ["2026-10-18", "old2", "None", "75", "alice"]])
        self.save(sheet, replace_legacy=True)
        self.assertEqual(len(sheet.rows), 3)
        self.assertEqual(sheet.rows[1][1], "old1")
        self.assertEqual(load_day(sheet, "alice", "2026-10-18")["food_log"], [FOOD])

    def test_unknown_schema_and_corrupt_json_raise_without_changes(self):
        sheet = Sheet([["unexpected"]])
        before = copy.deepcopy(sheet.rows)
        with self.assertRaises(ValueError):
            self.save(sheet)
        self.assertEqual(sheet.rows, before)
        sheet = Sheet()
        self.save(sheet)
        sheet.rows[1][5] = "broken json"
        with self.assertRaises(ValueError):
            load_day(sheet, "alice", "2026-10-18")

    def test_extra_columns_preserved(self):
        sheet = Sheet([HEADERS + ["Coach_Note"],
                       ["2026-10-18", "old", "None", "75", "alice", "Keep this"]])
        self.save(sheet, replace_legacy=True)
        self.assertEqual(sheet.rows[1][5], "Keep this")


if __name__ == "__main__":
    unittest.main()

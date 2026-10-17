import copy
import unittest
from profile_storage import ACTIVITIES, HEADERS, load_profile, save_profile
from test_tracker_storage import Sheet


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.sheet = Sheet([])

    def test_missing_profile_returns_none_without_writing(self):
        self.assertIsNone(load_profile(None, "alice"))
        self.assertIsNone(load_profile(self.sheet, "alice"))
        self.assertEqual(self.sheet.rows, [])

    def test_gspread_empty_sheet_shapes_allow_first_save_and_reload(self):
        for rows in [[], [[]], [[""]], [["", "", ""], ["", "", ""]]]:
            with self.subTest(rows=rows):
                sheet = Sheet(rows)
                self.assertIsNone(load_profile(sheet, "alice"))
                expected = save_profile(sheet, "alice", 164, 52, ACTIVITIES[0])
                self.assertEqual(sheet.rows[0], HEADERS)
                self.assertEqual(load_profile(sheet, "alice"), expected)

    def test_empty_header_with_nonempty_data_is_preserved(self):
        self.sheet.rows = [[], ["alice", "164", "52", ACTIVITIES[0], ""]]
        before = copy.deepcopy(self.sheet.rows)
        with self.assertRaises(ValueError):
            save_profile(self.sheet, "alice", 164, 52, ACTIVITIES[0])
        self.assertEqual(self.sheet.rows, before)

    def test_new_profile_roundtrips_numeric_values_as_returned_by_sheets(self):
        expected = save_profile(self.sheet, "alice", 162.5, 58.2, ACTIVITIES[1])
        self.sheet.rows[1] = [str(value) for value in self.sheet.rows[1]]
        self.assertEqual(load_profile(self.sheet, "alice"), expected)
        self.assertEqual(self.sheet.rows[0], HEADERS)

    def test_update_does_not_append_another_profile(self):
        save_profile(self.sheet, "alice", 160, 70, ACTIVITIES[0])
        save_profile(self.sheet, "alice", 161, 65, ACTIVITIES[1])
        self.assertEqual(len(self.sheet.rows), 2)
        self.assertEqual(load_profile(self.sheet, "alice")["weight_kg"], 65)

    def test_updating_one_student_preserves_other_student(self):
        save_profile(self.sheet, "alice", 160, 70, ACTIVITIES[0])
        save_profile(self.sheet, "bob", 180, 80, ACTIVITIES[1])
        previous = copy.deepcopy(self.sheet.rows[2])
        save_profile(self.sheet, "alice", 160, 60, ACTIVITIES[0])
        self.assertEqual(self.sheet.rows[2], previous)
        self.assertIsNone(load_profile(self.sheet, "charlie"))

    def test_invalid_inputs_do_not_write(self):
        for height, weight, activity in [(99, 70, ACTIVITIES[0]),
                                         (160, 201, ACTIVITIES[0]),
                                         (float("nan"), 70, ACTIVITIES[0]),
                                         (160, float("inf"), ACTIVITIES[0]),
                                         (160, 70, "Unknown")]:
            with self.subTest(height=height, weight=weight, activity=activity):
                with self.assertRaises(ValueError):
                    save_profile(self.sheet, "alice", height, weight, activity)
                self.assertEqual(self.sheet.rows, [])

    def test_unknown_columns_block_read_and_write(self):
        self.sheet.rows = [["unexpected"]]
        with self.assertRaises(ValueError):
            load_profile(self.sheet, "alice")
        with self.assertRaises(ValueError):
            save_profile(self.sheet, "alice", 160, 70, ACTIVITIES[0])
        self.assertEqual(self.sheet.rows, [["unexpected"]])

    def test_invalid_saved_profile_is_reported_instead_of_silent_defaults(self):
        self.sheet.rows = [HEADERS, ["alice", "broken", "70", ACTIVITIES[0], ""]]
        with self.assertRaises(ValueError):
            load_profile(self.sheet, "alice")


if __name__ == "__main__":
    unittest.main()

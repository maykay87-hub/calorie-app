import copy
import unittest
from tracker_history import load_history
from tracker_storage import HEADERS, save_day
from test_tracker_storage import Sheet, FOOD


class HistoryTests(unittest.TestCase):
    def test_latest_row_per_date_matches_editor_and_users_are_isolated(self):
        sheet = Sheet([HEADERS, ['2026-10-17', 'old', 'None', '20', 'alice'],
                       ['2026-10-17', 'latest', 'None', '50', 'alice'],
                       ['2026-10-18', 'private', 'None', '70', 'bob']])
        before = copy.deepcopy(sheet.rows)
        result = load_history(sheet, 'alice')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['Food_Log'], 'latest')
        self.assertEqual(result[0]['Net_Calories'], 50)
        self.assertIsNone(result[0]['Protein'])
        self.assertEqual(sheet.rows, before)

    def test_partial_protein_is_never_a_complete_daily_total(self):
        sheet = Sheet()
        missing = dict(FOOD, Protein=None)
        save_day(sheet, 'alice', '2026-10-18', [FOOD, missing], [], 150, 'rice', 'None')
        row = load_history(sheet, 'alice')[0]
        self.assertEqual(row['known_protein'], 2)
        self.assertEqual(row['missing_protein_entries'], 1)
        self.assertIsNone(row['Protein'])

    def test_complete_zero_and_empty_food_day_are_valid(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-17', [dict(FOOD, Protein=0)], [], 75, 'rice', 'None')
        save_day(sheet, 'alice', '2026-10-18', [], [], 0, 'None', 'None')
        result = load_history(sheet, 'alice')
        self.assertEqual([row['Date'] for row in result], ['2026-10-18', '2026-10-17'])
        self.assertEqual([row['Protein'] for row in result], [0, 0])

    def test_bad_details_do_not_hide_saved_summary_or_fabricate_macros(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], 75, 'rice', 'None')
        sheet.rows[1][5] = 'broken'
        row = load_history(sheet, 'alice')[0]
        self.assertEqual(row['status'], 'invalid_details')
        self.assertEqual(row['Net_Calories'], 75)
        self.assertEqual(row['Food_Log'], 'rice')
        self.assertIsNone(row['Protein'])

    def test_invalid_net_energy_is_not_charted_as_zero(self):
        for value in ['', 'oops', 'NaN', 'Infinity']:
            row = load_history(Sheet([HEADERS, ['2026-10-18', '', '', value, 'alice']]), 'alice')[0]
            self.assertIsNone(row['Net_Calories'])

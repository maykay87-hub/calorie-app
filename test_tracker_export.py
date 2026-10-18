import csv
import io
import json
import unittest
from tracker_export import export_history_csv, export_draft
from tracker_history import load_history
from tracker_storage import save_day
from test_tracker_storage import Sheet, FOOD


class ExportTests(unittest.TestCase):
    def test_csv_keeps_partial_protein_separate_and_excludes_other_accounts(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD, dict(FOOD, Protein=None)], [], 150, '白饭', 'None')
        save_day(sheet, 'bob', '2026-10-18', [FOOD], [], 75, 'private', 'None')
        data = export_history_csv(load_history(sheet, 'alice'))
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['Protein_complete_g'], '')
        self.assertEqual(rows[0]['Protein_known_g'], '2.0')
        self.assertEqual(rows[0]['Protein_missing_entries'], '1')
        self.assertEqual(rows[0]['Food_Log'], '白饭')
        self.assertNotIn('private', data.decode('utf-8-sig'))

    def test_csv_keeps_negative_net_numeric_and_formula_text_inert(self):
        sheet = Sheet()
        save_day(sheet, 'alice', '2026-10-18', [FOOD], [], -25, '=SUM(1,2)', '  +formula')
        rows = list(csv.DictReader(io.StringIO(export_history_csv(load_history(sheet, 'alice')).decode('utf-8-sig'))))
        self.assertEqual(rows[0]['Net_Calories_kcal'], '-25.0')
        self.assertEqual(rows[0]['Food_Log'], "'=SUM(1,2)")
        self.assertTrue(rows[0]['Exercise_Log'].startswith("'"))

    def test_draft_backup_has_only_account_date_and_entries_with_unknowns_preserved(self):
        food = dict(FOOD, Protein=None, Source={'status': 'published_energy_reference'})
        backup = json.loads(export_draft('alice', '2026-10-18', [food], []))
        self.assertEqual(set(backup), {'schema_version', 'username', 'date', 'food_log', 'exercise_log'})
        self.assertEqual(backup['username'], 'alice')
        self.assertIsNone(backup['food_log'][0]['Protein'])
        self.assertEqual(backup['food_log'][0]['Source'], food['Source'])

import unittest
from coach_feedback import load_feedback, publish_feedback, review_period, HEADERS
from test_tracker_storage import Sheet


class FeedbackTests(unittest.TestCase):
    def test_periods_and_legacy_rows_sort_without_cross_account_leak(self):
        week = review_period('weekly', '2026-10-21')
        self.assertEqual(week, 'Week 2026-10-19 — 2026-10-25')
        self.assertEqual(review_period('monthly', '2026-10-21'), '2026-10')
        sheet = Sheet([HEADERS, ['a', week, 'Newest week'],
                       ['b', week, 'Private'], ['a', '2026-09', 'Old month'],
                       ['a', 'August', 'Legacy month']])
        result = load_feedback(sheet, 'a')
        self.assertEqual([r['note'] for r in result], ['Newest week', 'Old month', 'Legacy month'])

    def test_retry_and_revision_keep_original_rows(self):
        sheet = Sheet([HEADERS])
        publish_feedback(sheet, 'a', '2026-10', '=literal text')
        self.assertEqual(publish_feedback(sheet, 'a', '2026-10', '=literal text'), 'unchanged')
        publish_feedback(sheet, 'a', '2026-10', 'Revised note')
        self.assertEqual(len(sheet.rows), 3)
        self.assertEqual(sheet.rows[1][-1], '=literal text')
        self.assertEqual(load_feedback(sheet, 'a')[0]['note'], 'Revised note')

    def test_malformed_headers_and_blank_notes_never_write(self):
        sheet = Sheet([['wrong'], ['preserve me']])
        before = sheet.get_all_values()
        with self.assertRaises(ValueError):
            publish_feedback(sheet, 'a', '2026-10', 'Review')
        self.assertEqual(sheet.rows, before)
        with self.assertRaises(ValueError):
            publish_feedback(Sheet([HEADERS]), 'a', '2026-10', ' ')

    def test_empty_sheets_and_extended_columns_preserve_schema(self):
        for rows in ([], [[]]):
            sheet = Sheet(rows)
            publish_feedback(sheet, 'a', '2026-10', 'Review')
            self.assertEqual(load_feedback(sheet, 'a')[0]['note'], 'Review')
        sheet = Sheet([['note', 'custom', 'month', 'username'], ['Old', 'kept', '2026-09', 'a']])
        publish_feedback(sheet, 'a', '2026-10', 'New')
        self.assertEqual(sheet.rows[1][1], 'kept')
        self.assertEqual(sheet.rows[2], ['New', '', '2026-10', 'a'])


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import unittest
from unittest.mock import patch
from deployment_config import resolve_spreadsheet_id


class DeploymentIsolationTests(unittest.TestCase):
    def test_production_keeps_its_existing_explicit_database(self):
        self.assertEqual(resolve_spreadsheet_id({'spreadsheet_id': 'student-book'}), 'student-book')

    def test_staging_never_falls_back_to_an_existing_student_database(self):
        for config in ({}, {'spreadsheet_id': 'student-book'},
                       {'staging_spreadsheet_id': 'test-book'},
                       {'production_spreadsheet_id': 'student-book'}):
            with self.assertRaises(ValueError):
                resolve_spreadsheet_id(config, 'staging')

    def test_staging_rejects_either_declared_student_database(self):
        for testing in ('student-book', 'other-student-book'):
            with self.assertRaises(ValueError):
                resolve_spreadsheet_id({'staging_spreadsheet_id': testing,
                                       'production_spreadsheet_id': 'student-book',
                                       'spreadsheet_id': 'other-student-book'}, 'staging')

    def test_staging_uses_only_its_independent_database(self):
        config = {'production_spreadsheet_id': 'student-book', 'spreadsheet_id': 'student-book',
                  'staging_spreadsheet_id': 'test-book'}
        self.assertEqual(resolve_spreadsheet_id(config, 'staging'), 'test-book')

    def test_invalid_environment_stops_instead_of_using_production(self):
        with self.assertRaises(ValueError):
            resolve_spreadsheet_id({'spreadsheet_id': 'student-book'}, 'invalid')

    def test_staging_entry_stops_before_google_when_not_configured(self):
        from streamlit.testing.v1 import AppTest
        with patch('gspread.authorize', side_effect=AssertionError('No database connection allowed')):
            app = AppTest.from_file(str(Path(__file__).with_name('staging.app.py')), default_timeout=15)
            app.secrets['spreadsheet_id'] = 'student-book'
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Staging requires' in error.value for error in app.error))

    def test_staging_demo_is_also_independent_of_google(self):
        from streamlit.testing.v1 import AppTest
        with patch('gspread.authorize', side_effect=AssertionError('Demo cannot connect to Google')):
            app = AppTest.from_file(str(Path(__file__).with_name('staging.app.py')), default_timeout=15)
            app.query_params['demo'] = '1'
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any('公开体验' in item.value for item in app.info))

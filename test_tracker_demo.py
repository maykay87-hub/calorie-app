from pathlib import Path
import unittest
from unittest.mock import patch


class DemoTests(unittest.TestCase):
    def test_demo_works_without_secrets_or_any_google_connection(self):
        from streamlit.testing.v1 import AppTest
        with patch('gspread.authorize', side_effect=AssertionError('Demo must never connect to Google')):
            app = AppTest.from_file(str(Path(__file__).with_name('advancedplus.app.py')), default_timeout=15)
            app.query_params['demo'] = '1'
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.text_input)
            next(b for b in app.button if b.label.startswith('Add Meal')).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state['demo_foods']), 1)
            next(b for b in app.button if b.label.startswith('体验保存')).click().run()
            self.assertTrue(any('不写入云端' in s.value for s in app.success))
            next(b for b in app.button if b.label.startswith('加入示范运动')).click().run()
            self.assertEqual(app.session_state['demo_burned'], 100)
            next(b for b in app.button if b.label.startswith('重新体验')).click().run()
            self.assertEqual(app.session_state['demo_foods'], [])
            self.assertEqual(app.session_state['demo_burned'], 0)

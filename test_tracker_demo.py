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
            next(b for b in app.button if b.label.startswith('添加运动')).click().run()
            self.assertEqual(app.session_state['demo_burned'], 100)
            next(b for b in app.button if b.label.startswith('重新体验')).click().run()
            self.assertEqual(app.session_state['demo_foods'], [])
            self.assertEqual(app.session_state['demo_burned'], 0)

    def test_demo_profile_undo_date_and_saved_history_match_student_flow(self):
        from datetime import timedelta
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).with_name('advancedplus.app.py')), default_timeout=15)
        app.query_params['demo'] = '1'
        app.run()
        first = app.date_input(key='demo_date').value
        app.selectbox(key='demo_activity').set_value('Active (x30)')
        next(b for b in app.button if b.label.startswith('保存示范资料')).click().run()
        self.assertEqual(app.session_state['demo_profile']['activity'], 'Active (x30)')
        self.assertEqual(next(m.value for m in app.metric if 'Demo target' in m.label), '1,800 kcal')
        next(b for b in app.button if b.label.startswith('Add Meal')).click().run()
        next(b for b in app.button if b.label == '撤销上一笔 · Undo').click().run()
        self.assertEqual(app.session_state['demo_foods'], [])
        next(b for b in app.button if b.label.startswith('Add Meal')).click().run()
        next(b for b in app.button if b.label.startswith('体验保存')).click().run()
        self.assertIn(str(first), app.session_state['demo_saved'])
        app.date_input(key='demo_date').set_value(first - timedelta(days=1)).run()
        self.assertEqual(app.session_state['demo_foods'], [])
        next(b for b in app.button if b.label.startswith('打开这一天')).click().run()
        self.assertEqual(app.date_input(key='demo_date').value, first)
        self.assertEqual(len(app.session_state['demo_foods']), 1)
        self.assertFalse(app.exception)

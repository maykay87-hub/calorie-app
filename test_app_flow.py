"""Real Streamlit widget flows against in-memory Sheets; no credentials/network."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import unittest
from unittest.mock import patch
from test_tracker_storage import Sheet, HEADERS
from profile_storage import HEADERS as PROFILE_HEADERS


class RecordSheet(Sheet):
    def get_all_records(self):
        return [dict(zip(self.rows[0], row)) for row in self.rows[1:]]


@unittest.skipUnless(importlib.util.find_spec('streamlit') and importlib.util.find_spec('gspread') and importlib.util.find_spec('oauth2client'), 'Streamlit app dependencies not installed')
class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.sheet = RecordSheet([HEADERS])
        profiles = RecordSheet([PROFILE_HEADERS, ['student', '162', '52', 'Sedentary (x25)', '']])
        feedback = RecordSheet([['username', 'month', 'note']])
        book = SimpleNamespace(get_worksheet=lambda i: self.sheet,
                               worksheet=lambda name: profiles if name == 'profiles' else feedback)
        client = SimpleNamespace(open_by_key=lambda key: book)
        self.auth = patch('gspread.authorize', return_value=client)
        self.creds = patch('oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_dict', return_value=object())
        self.auth.start(); self.creds.start()
        self.addCleanup(self.auth.stop); self.addCleanup(self.creds.stop)
        self.at = self.new_app()

    def new_app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).with_name('advancedplus.app.py')), default_timeout=15)
        app.secrets['spreadsheet_id'] = 'test-only'
        app.secrets['service_account'] = {}
        app.session_state['logged_in'] = True
        app.session_state['username'] = 'student'
        app.run()
        self.assertFalse(app.exception)
        return app

    def number(self, prefix):
        return next(x for x in self.at.number_input if x.label.startswith(prefix))

    def button(self, prefix):
        return next(x for x in self.at.button if x.label.startswith(prefix))

    def add_package(self):
        self.at.selectbox(key='label_unit').set_value('g').run()
        next(x for x in self.at.text_input if x.label.startswith('产品名称')).set_value('Wholemeal bread')
        self.number('实际食用量（').set_value(30.0)
        self.number('标签热量').set_value(240.0)
        self.number('标签蛋白质').set_value(10.0)
        self.button('添加标签记录').click().run()
        self.assertFalse(self.at.exception)

    def test_label_edit_save_and_new_session_restore(self):
        self.add_package()
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertIsNone(self.at.session_state['food_log'][0]['Carbs'])
        self.assertTrue(any('Unsaved' in x.value for x in self.at.warning))
        self.number('实际食用量 ·').set_value(60.0)
        self.button('更新份数').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Protein'], 6)
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertFalse(any('Unsaved changes' in x.value for x in self.at.warning))
        self.assertEqual(len(self.sheet.rows), 2)
        restored = self.new_app()
        self.assertEqual(restored.session_state['food_log'][0]['Calories'], 144)
        self.assertIsNone(restored.session_state['food_log'][0]['Carbs'])

    def test_empty_label_rejects_add_and_zero_edit_keeps_record(self):
        self.button('添加标签记录').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'], [])
        self.add_package()
        self.number('实际食用量 ·').set_value(0.0)
        self.button('更新份数').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertTrue(any('greater than zero' in x.value for x in self.at.error))
        self.button('删除这一笔').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'], [])

    def test_search_and_selection_changes_render_without_widget_errors(self):
        self.at.text_input(key='food_search').set_value('nasilemak').run()
        self.assertFalse(self.at.exception)
        self.assertIn('Nasi Lemak', self.at.selectbox(key='selected_food_id').value)
        self.at.text_input(key='food_search').set_value('no-food-matches-here').run()
        self.assertFalse(self.at.exception)
        self.at.text_input(key='food_search').set_value('dry wantan').run()
        self.assertFalse(self.at.exception)
        self.assertIn('Wantan Mee Dry', self.at.selectbox(key='selected_food_id').value)

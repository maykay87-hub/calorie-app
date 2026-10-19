"""Real Streamlit widget flows against in-memory Sheets; no credentials/network."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import unittest
from unittest.mock import patch
from test_tracker_storage import Sheet, HEADERS, FOOD
from tracker_storage import save_day
from profile_storage import HEADERS as PROFILE_HEADERS
from student_notes import NOTE_HEADERS, FILE_HEADERS
from test_student_notes import NoteSheet


class RecordSheet(Sheet):
    def get_all_records(self):
        return [dict(zip(self.rows[0], row)) for row in self.rows[1:]]


@unittest.skipUnless(importlib.util.find_spec('streamlit') and importlib.util.find_spec('gspread') and importlib.util.find_spec('oauth2client'), 'Streamlit app dependencies not installed')
class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.sheet = RecordSheet([HEADERS])
        self.profiles = RecordSheet([PROFILE_HEADERS, ['student', '162', '52', 'Sedentary (x25)', '']])
        feedback = self.feedback = RecordSheet([['username', 'month', 'note']])
        self.notes = NoteSheet([NOTE_HEADERS])
        self.attachments = NoteSheet([FILE_HEADERS])
        book = SimpleNamespace(get_worksheet=lambda i: self.sheet,
            worksheet=lambda name: {'profiles': self.profiles, 'feedback': feedback,
                                    'student_notes': self.notes, 'student_attachments': self.attachments}[name])
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
        app.secrets['passwords'] = {'student': 'test-pass', 'another': 'other-pass'}
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

    def test_remarks_save_restore_pause_remaining_and_reach_coach(self):
        next(x for x in self.at.text_area if x.label.startswith('备注')).set_value('Half bowl pan mee; food not found')
        next(b for b in self.at.button if b.label.startswith('保存补充记录')).click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.notes.rows), 2)
        self.assertTrue(any('Food calories are incomplete' in x.value for x in self.at.info))
        self.assertFalse(any('kcal remaining' in x.value for x in self.at.markdown))
        restored = self.new_app()
        self.assertTrue(any('Half bowl pan mee' in x.value for x in restored.text))
        self.at.secrets['passwords'] = {'student': 'test-pass', 'admin': 'coach-pass'}
        self.at.session_state['username'] = 'admin'
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('Half bowl pan mee' in x.value for x in self.at.text))

    def test_attachment_form_persists_and_can_be_downloaded_after_new_session(self):
        upload = SimpleNamespace(name='sample-label.pdf', getvalue=lambda: b'%PDF-1.7\nExample only')
        with patch('streamlit.file_uploader', return_value=[upload]):
            self.at.run()
            next(b for b in self.at.button if b.label.startswith('保存补充记录')).click().run()
        self.assertFalse(self.at.exception)
        self.assertGreater(len(self.attachments.rows), 1)
        restored = self.new_app()
        self.assertTrue(any('sample-label.pdf' in x.value for x in restored.text))
        next(b for b in restored.button if b.label.startswith('准备下载附件')).click().run()
        self.assertFalse(restored.exception)
        self.assertEqual(len(restored.get('download_button')), 1)

    def test_coach_can_select_remarks_only_student_when_other_students_have_logs(self):
        save_day(self.sheet, 'another', date.today(), [FOOD], [], 75, 'other rice', 'None')
        next(x for x in self.at.text_area if x.label.startswith('备注')).set_value('Remarks without a calorie log')
        next(b for b in self.at.button if b.label.startswith('保存补充记录')).click().run()
        self.at.secrets['passwords'] = {'student': 'test-pass', 'another': 'other-pass', 'admin': 'coach-pass'}
        self.at.session_state['username'] = 'admin'
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertIn('student', self.at.selectbox(key='coach_student').options)
        self.at.selectbox(key='coach_student').set_value('student').run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('Remarks without a calorie log' in x.value for x in self.at.text))

    def test_pending_food_can_be_marked_counted_only_after_saved_food(self):
        next(x for x in self.at.text_area if x.label.startswith('备注')).set_value('Missing food')
        next(b for b in self.at.button if b.label.startswith('保存补充记录')).click().run()
        next(b for b in self.at.button if b.label.startswith('已补齐饮食')).click().run()
        self.assertTrue(any('Add and save' in x.value for x in self.at.error))
        self.button('Add Meal').click().run()
        self.at.button(key='save_bottom_food').click().run()
        next(b for b in self.at.button if b.label.startswith('已补齐饮食')).click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('kcal remaining' in x.value for x in self.at.markdown))
        self.assertTrue(any('Missing food' in x.value for x in self.at.text))

    def test_failed_remark_save_keeps_input_and_food_flow(self):
        remark = next(x for x in self.at.text_area if x.label.startswith('备注'))
        remark.set_value('Please check this food')
        with patch.object(self.notes, 'append_row', side_effect=ConnectionError('offline')):
            next(b for b in self.at.button if b.label.startswith('保存补充记录')).click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(next(x for x in self.at.text_area if x.label.startswith('备注')).value, 'Please check this food')
        self.assertEqual(len(self.notes.rows), 1)
        self.button('Add Meal').click().run()
        self.assertEqual(len(self.at.session_state['food_log']), 1)

    def test_student_feedback_is_account_scoped_and_refreshes(self):
        self.feedback.rows += [['another', '2026-10', 'Other private note'],
                               ['student', '2026-10', 'Add vegetables next week.']]
        self.at.button(key='refresh_feedback').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('Add vegetables' in x.value for x in self.at.text))
        self.assertFalse(any('Other private' in x.value for x in self.at.text))
        self.assertEqual(self.at.session_state['food_log'], [])

    def test_coach_publishes_review_and_student_can_read_it(self):
        self.at.secrets['passwords'] = {'student': 'test-pass', 'admin': 'coach-pass'}
        self.at.session_state['username'] = 'admin'
        self.at.run()
        self.assertFalse(self.at.exception)
        self.at.text_area(key='review_body_student').set_value('Keep your regular breakfast; add vegetables at lunch.')
        next(b for b in self.at.button if b.label.startswith('发布给这位')).click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.feedback.rows), 2)
        self.assertEqual(self.feedback.rows[1][0], 'student')
        self.assertTrue(self.feedback.rows[1][1].startswith('Week '))
        next(b for b in self.at.button if b.label.startswith('发布给这位')).click().run()
        self.assertEqual(len(self.feedback.rows), 2)
        restored = self.new_app()
        self.assertTrue(any('regular breakfast' in x.value for x in restored.text))

    def test_same_period_feedback_supplements_remain_readable(self):
        self.feedback.rows = [['username', 'month', 'note', 'published_at'],
                             ['student', '2026-10', 'First personalised review', '2026-10-19T16:00:00+08:00'],
                             ['student', '2026-10', 'Later personalised supplement', '2026-10-19T16:30:00+08:00']]
        self.at.button(key='refresh_feedback').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('Later personalised supplement' in x.value for x in self.at.text))
        self.assertTrue(any('First personalised review' in x.value for x in self.at.text))
        self.assertTrue(any('2026-10-19 16:00' in x.value for x in self.at.caption))
        self.assertTrue(any('2026-10-19 16:30' in x.value for x in self.at.caption))

    def test_feedback_failure_keeps_food_entry_available(self):
        with patch.object(self.feedback, 'get_all_values', side_effect=ConnectionError('offline')):
            self.at.run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('Could not load feedback' in w.value for w in self.at.warning))
        self.button('Add Meal').click().run()
        self.assertEqual(len(self.at.session_state['food_log']), 1)

    def test_label_edit_save_and_new_session_restore(self):
        self.add_package()
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertIsNone(self.at.session_state['food_log'][0]['Carbs'])
        self.assertTrue(any('Unsaved' in x.value for x in self.at.warning))
        self.number('实际食用量 ·').set_value(60.0)
        self.button('更新这一笔').click().run()
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
        self.button('更新这一笔').click().run()
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

    def test_date_switch_keeps_separate_drafts_and_history_open_preserves_them(self):
        self.add_package()
        first = self.at.date_input(key='entry_date').value
        other = first - timedelta(days=1)
        self.at.date_input(key='entry_date').set_value(other).run()
        self.assertEqual(self.at.session_state['food_log'], [])
        self.button('Add Meal').click().run()
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.at.date_input(key='entry_date').set_value(first).run()
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.button('打开这一天').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.date_input(key='entry_date').value, other)
        self.at.date_input(key='entry_date').set_value(first).run()
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)

    def test_failed_save_keeps_draft_and_retry_updates_single_row(self):
        self.add_package()
        with patch.object(self.sheet, 'append_row', side_effect=ConnectionError('offline')):
            self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertTrue(any('Save was not confirmed' in x.value for x in self.at.error))
        self.assertTrue(any('Unsaved changes' in x.value for x in self.at.warning))
        self.at.button(key='save_bottom_food').click().run()
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.sheet.rows), 2)

    def test_retry_after_lost_save_ack_does_not_append_duplicate(self):
        self.add_package()
        append = self.sheet.append_row
        def write_then_timeout(*args, **kwargs):
            append(*args, **kwargs)
            raise TimeoutError('Acknowledgement was lost')
        with patch.object(self.sheet, 'append_row', side_effect=write_then_timeout):
            self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.sheet.rows), 2)
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.sheet.rows), 2)

    def test_logout_login_does_not_show_previous_accounts_data(self):
        self.add_package()
        self.button('Log Out').click().run()
        self.assertFalse(self.at.exception)
        with self.assertRaises(KeyError):
            self.at.session_state['food_log']
        self.at.text_input(key='login_user').set_value('another')
        self.at.text_input(key='login_pass').set_value('other-pass')
        self.at.button(key='login_btn').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'], [])
        self.assertEqual(self.at.session_state['username'], 'another')
        self.assertEqual(self.at.session_state['personal_labels'], [])

    def test_exercise_edit_and_delete_recalculate_net(self):
        self.add_package()
        self.button('添加运动').click().run()
        self.assertEqual(len(self.at.session_state['exercise_log']), 1)
        self.number('运动分钟').set_value(60.0)
        self.button('更新时长').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['exercise_log'][0]['Duration'], 60)
        self.at.button(key='save_bottom_exercise').click().run()
        self.assertLess(float(self.sheet.rows[-1][3]), 0)
        self.button('删除这一笔运动').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['exercise_log'], [])

    def test_edit_meal_and_remove_last_selected_row_without_widget_error(self):
        self.add_package()
        self.button('Add Meal').click().run()
        edit_key = f"food_edit_index_{self.at.date_input(key='entry_date').value}"
        self.at.selectbox(key=edit_key).set_value(1).run()
        self.button('撤销上一笔').click().run()
        self.assertFalse(self.at.exception)
        next(x for x in self.at.selectbox if x.label == '修改餐次 · Meal').set_value('Dinner')
        self.button('更新这一笔').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Meal'], 'Dinner')

    def test_legacy_day_cannot_be_overwritten_without_explicit_choice(self):
        day = str(self.at.date_input(key='entry_date').value)
        self.sheet.rows.append([day, 'Original text summary', 'None', '75', 'student'])
        self.at = self.new_app()
        self.assertTrue(self.at.button(key='save_bottom_food').disabled)
        self.add_package()
        self.assertTrue(self.at.button(key='save_bottom_food').disabled)
        self.assertEqual(self.sheet.rows[1][1], 'Original text summary')
        self.at.checkbox(key=f'replace_legacy_{day}').check().run()
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.sheet.rows), 2)
        self.assertIn('Wholemeal bread', self.sheet.rows[1][1])

    def test_profile_failure_does_not_block_daily_save_and_retry_recovers(self):
        with patch.object(self.profiles, 'get_all_values', side_effect=ValueError('Unexpected profile columns.')):
            self.at = self.new_app()
            self.assertTrue(any('Profile error' in x.value for x in self.at.error))
            self.add_package()
            self.at.button(key='save_bottom_food').click().run()
            self.assertFalse(self.at.exception)
            self.assertEqual(len(self.sheet.rows), 2)
        self.button('重试读取资料').click().run()
        self.assertFalse(self.at.exception)
        self.assertFalse(any('Profile error' in x.value for x in self.at.error))
        self.assertEqual(self.number('身高').value, 162)

    def test_profile_save_is_restored_without_changing_daily_records(self):
        self.add_package()
        self.at.button(key='save_bottom_food').click().run()
        before = [row[:] for row in self.sheet.rows]
        self.number('身高').set_value(165.0)
        self.number('体重').set_value(55.0)
        self.button('保存个人资料').click().run()
        self.assertFalse(self.at.exception)
        restored = self.new_app()
        self.assertEqual(next(x for x in restored.number_input if x.label.startswith('身高')).value, 165)
        self.assertEqual(next(x for x in restored.number_input if x.label.startswith('体重')).value, 55)
        self.assertEqual(self.sheet.rows, before)

    def test_integer_snapshot_and_older_meal_name_can_be_resaved(self):
        day = self.at.date_input(key='entry_date').value
        save_day(self.sheet, 'student', day, [dict(FOOD, Meal='Brunch')], [], 75, 'Rice', 'None')
        self.at = self.new_app()
        self.assertFalse(self.at.exception)
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('已保存' in x.value for x in self.at.success))
        self.assertEqual(len(self.sheet.rows), 2)

    def test_whole_meal_protein_reference_survives_half_serving_save_and_reload(self):
        self.at.text_input(key='food_search').set_value('dry wantan').run()
        self.assertIn('HPB SG reference', self.at.selectbox(key='selected_food_id').value)
        self.number('份数 · Servings').set_value(.5)
        self.button('Add Meal').click().run()
        self.assertFalse(self.at.exception)
        entry = self.at.session_state['food_log'][0]
        self.assertEqual(entry['Calories'], 312.5)
        self.assertAlmostEqual(entry['Protein'], 16.86)
        self.assertEqual(entry['Source']['region'], 'Singapore')
        self.at.button(key='save_bottom_food').click().run()
        restored = self.new_app()
        self.assertEqual(restored.session_state['food_log'][0], entry)

    def test_saved_package_can_be_reused_on_another_date_without_retyping_label(self):
        self.add_package()
        self.at.button(key='save_bottom_food').click().run()
        self.at = self.new_app()
        other = self.at.date_input(key='entry_date').value - timedelta(days=1)
        self.at.date_input(key='entry_date').set_value(other).run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'], [])
        self.number('这次食用量').set_value(50.0)
        self.button('添加我的食品').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 120)
        self.assertEqual(self.at.session_state['food_log'][0]['Protein'], 5)
        self.assertIsNone(self.at.session_state['food_log'][0]['Carbs'])

    def test_personal_label_is_searchable_and_uses_label_provenance(self):
        self.add_package()
        self.at.text_input(key='food_search').set_value('Wholemeal bread').run()
        selected = next(key for key in self.at.session_state['personal_labels'] if key['Source']['product_name'] == 'Wholemeal bread')
        self.at.selectbox(key='selected_food_id').set_value(selected['Food'])
        self.number('份数 · Servings').set_value(0.2)
        self.button('Add Meal').click().run()
        self.assertFalse(self.at.exception)
        added = self.at.session_state['food_log'][-1]
        self.assertEqual(added['Calories'], 48)
        self.assertEqual(added['Source']['status'], 'user_entered_package_label')

    def test_volume_reference_renders_and_saves_without_treating_ml_as_grams(self):
        self.at.text_input(key='food_search').set_value('low fat milk').run()
        self.assertFalse(self.at.exception)
        self.assertIn('250 ml', self.at.selectbox(key='selected_food_id').value)
        self.button('Add Meal').click().run()
        self.assertFalse(self.at.exception)
        entry = self.at.session_state['food_log'][0]
        self.assertEqual(entry['Calories'], 118)
        self.assertEqual(entry['Protein'], 8.7)
        self.assertEqual(entry['Source']['portion_unit'], 'ml')
        self.assertIsNone(entry['Source']['weight_g_per_serving'])

    def test_no_added_sugar_milk_coffee_keeps_its_published_energy(self):
        self.at.text_input(key='food_search').set_value('kopi c kosong').run()
        self.assertFalse(self.at.exception)
        self.assertIn('Kopi C Kosong', self.at.selectbox(key='selected_food_id').value)
        self.button('Add Meal').click().run()
        self.assertFalse(self.at.exception)
        entry = self.at.session_state['food_log'][0]
        self.assertEqual(entry['Calories'], 93)
        self.assertEqual(entry['Carbs'], 12.1)
        self.assertEqual(entry['Source']['portion_unit'], 'ml')

    def test_clear_saved_food_then_undo_can_restore_and_resave(self):
        self.add_package()
        self.at.button(key='save_bottom_food').click().run()
        self.button('清空当天饮食').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'], [])
        self.assertFalse(self.button('撤销上一笔 · Undo').disabled)
        self.at.button(key='save_bottom_food').click().run()
        self.button('撤销上一笔 · Undo').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertTrue(any('Unsaved changes' in x.value for x in self.at.warning))
        self.at.button(key='save_bottom_food').click().run()
        restored = self.new_app()
        self.assertEqual(restored.session_state['food_log'][0]['Calories'], 72)

    def test_clear_exercise_keeps_undo_available_when_list_is_empty(self):
        self.button('添加运动').click().run()
        before = self.at.session_state['exercise_log'][0].copy()
        self.button('清空当天运动').click().run()
        self.assertEqual(self.at.session_state['exercise_log'], [])
        self.button('撤销上一笔运动').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['exercise_log'], [before])

    def test_second_page_conflict_preserves_local_draft_until_confirmed_reload(self):
        first = self.at
        second = self.new_app()
        self.at = first
        self.add_package()
        self.at.button(key='save_bottom_food').click().run()
        self.at = second
        self.button('添加运动').click().run()
        local_exercise = self.at.session_state['exercise_log'][0].copy()
        self.at.button(key='save_bottom_exercise').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any('changed elsewhere' in x.value for x in self.at.error))
        self.assertEqual(self.at.session_state['exercise_log'], [local_exercise])
        self.assertTrue(self.at.button(key='save_bottom_exercise').disabled)
        self.assertTrue(self.button('载入云端最新版').disabled)
        self.assertEqual(json.loads(self.sheet.rows[1][5])[0]['Calories'], 72)
        day = self.at.date_input(key='entry_date').value
        self.at.checkbox(key=f'reload_conflict_{day}').check().run()
        self.button('载入云端最新版').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state['food_log'][0]['Calories'], 72)
        self.assertEqual(self.at.session_state['exercise_log'], [])
        self.assertFalse(self.at.button(key='save_bottom_exercise').disabled)

    def test_quarter_serving_and_short_exercise_save_restore(self):
        self.at.text_input(key='food_search').set_value('dry wantan').run()
        self.number('份数 · Servings').set_value(.25)
        self.button('Add Meal').click().run()
        food = self.at.session_state['food_log'][0].copy()
        self.assertEqual(food['Qty'], .25)
        self.assertAlmostEqual(food['Calories'], 156.25)
        self.assertAlmostEqual(food['Protein'], 8.43)
        self.number('时长（分钟）').set_value(10)
        self.button('添加运动').click().run()
        exercise = self.at.session_state['exercise_log'][0].copy()
        self.assertEqual(exercise['Duration'], 10)
        self.at.button(key='save_bottom_exercise').click().run()
        restored = self.new_app()
        self.assertEqual(restored.session_state['food_log'][0], food)
        self.assertEqual(restored.session_state['exercise_log'][0], exercise)

    def test_pending_day_navigation_preserves_draft_and_clears_after_save(self):
        day = self.at.date_input(key='entry_date').value
        self.button('Add Meal').click().run()
        food = self.at.session_state['food_log'][0].copy()
        self.assertTrue(self.at.button(key=f'pending_day_{day}').disabled)
        self.at.date_input(key='entry_date').set_value(day - timedelta(days=1)).run()
        self.assertEqual(self.at.session_state['food_log'], [])
        self.at.button(key=f'pending_day_{day}').click().run()
        self.assertEqual(self.at.date_input(key='entry_date').value, day)
        self.assertEqual(self.at.session_state['food_log'], [food])
        self.at.button(key='save_bottom_food').click().run()
        self.assertFalse(self.at.exception)
        self.assertFalse(any(x.key == f'pending_day_{day}' for x in self.at.button))

    def test_coach_selects_one_student_and_latest_saved_day(self):
        day = self.at.date_input(key='entry_date').value
        save_day(self.sheet, 'student', day, [FOOD], [], 75, 'student rice', 'None')
        save_day(self.sheet, 'another', day, [dict(FOOD, Protein=None)], [], 75, 'other rice', 'None')
        self.at.session_state['username'] = 'admin'
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.selectbox(key='coach_student').value, 'another')
        self.assertIn('other rice', self.at.dataframe[0].value.to_string())
        self.assertNotIn('student rice', self.at.dataframe[0].value.to_string())
        self.at.selectbox(key='coach_student').set_value('student').run()
        self.assertFalse(self.at.exception)
        self.assertIn('student rice', self.at.dataframe[0].value.to_string())
        self.assertNotIn('other rice', self.at.dataframe[0].value.to_string())

    def test_new_profile_does_not_use_default_values_for_target(self):
        self.profiles.rows = [PROFILE_HEADERS]
        self.at = self.new_app()
        self.assertFalse(any(x.label == '🔥 Daily Target' for x in self.at.metric))
        self.button('Add Meal').click().run()
        self.assertEqual(len(self.at.session_state['food_log']), 1)
        self.number('身高').set_value(164.0).run()
        self.number('体重').set_value(52.0).run()
        self.assertFalse(any(x.label == '🔥 Daily Target' for x in self.at.metric))
        self.button('保存个人资料').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(next(x.value for x in self.at.metric if x.label == '🔥 Daily Target'), '1300 kcal')

    def test_unsaved_profile_changes_keep_saved_energy_target(self):
        self.assertEqual(next(x.value for x in self.at.metric if x.label == '🔥 Daily Target'), '1300 kcal')
        self.number('体重').set_value(50.0).run()
        self.assertEqual(next(x.value for x in self.at.metric if x.label == '🔥 Daily Target'), '1300 kcal')
        self.assertTrue(any('Save profile changes' in x.value for x in self.at.caption))
        self.button('保存个人资料').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(next(x.value for x in self.at.metric if x.label == '🔥 Daily Target'), '1250 kcal')

    def test_login_form_rejects_wrong_password_then_clears_successful_credentials(self):
        self.button('Log Out').click().run()
        self.at.text_input(key='login_user').set_value(' student ')
        self.at.text_input(key='login_pass').set_value('wrong')
        self.button('登入').click().run()
        self.assertFalse(self.at.session_state['logged_in'])
        self.assertTrue(any('Incorrect username or password' in x.value for x in self.at.error))
        self.assertEqual(len(self.at.dataframe), 0)
        self.at.text_input(key='login_pass').set_value('test-pass')
        self.button('登入').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(self.at.session_state['logged_in'])
        self.assertEqual(self.at.session_state['username'], 'student')
        self.assertNotIn('login_pass', self.at.session_state)
        self.assertNotIn('login_user', self.at.session_state)
        self.button('Log Out').click().run()
        self.assertEqual(self.at.text_input(key='login_pass').value, '')

    def test_simple_food_form_logs_without_search_or_custom_food_input(self):
        self.assertFalse(self.at.exception)
        self.assertFalse(any('Saved profile loads' in x.value for x in self.at.caption))
        self.assertFalse(any('营养合计与完整度' in x.label for x in self.at.expander))
        self.number('份数 · Servings').set_value(0.5)
        self.button('Add Meal').click().run()
        self.assertEqual(len(self.at.session_state['food_log']), 1)
        self.assertEqual(self.at.session_state['food_log'][0]['Qty'], 0.5)
        self.assertEqual(list(self.at.dataframe[0].value.columns), ['餐次 Meal', '食物 Food', '食用量 Amount', 'kcal'])

    def test_remaining_is_prominent_and_nutrient_values_survive_calorie_only_view(self):
        self.add_package()
        html = '\n'.join(x.value for x in self.at.markdown)
        self.assertIn('kcal remaining · 今日剩余', html)
        self.assertIn('Food Intake', html)
        self.assertIn('Exercise Burn', html)
        self.assertEqual(self.at.session_state['food_log'][0]['Protein'], 3)
        self.assertIsNone(self.at.session_state['food_log'][0]['Carbs'])
        self.assertFalse(any('Recorded protein' in x.value for x in self.at.info))

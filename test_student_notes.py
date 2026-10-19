import copy
import re
import unittest
from unittest.mock import patch
from student_notes import (NOTE_HEADERS, FILE_HEADERS, MAX_FILE_BYTES, prepare_note,
                           save_note, load_notes, download_attachment, mark_note_counted, annotate_energy_status)
from test_tracker_storage import Sheet


class NoteSheet(Sheet):
    def get(self, range_name):
        match = re.search(r'A(\d+):[A-Z]+(\d+)', range_name)
        return copy.deepcopy(self.rows[int(match[1]) - 1:int(match[2])])

    def update(self, range_name, values, value_input_option):
        if range_name.startswith('H'):
            index = int(range_name[1:]) - 1
            self.rows[index] += [''] * (8 - len(self.rows[index]))
            self.rows[index][7] = values[0][0]
        else:
            super().update(range_name, values, value_input_option)

    def append_rows(self, values, value_input_option):
        start = len(self.rows) + 1
        self.rows.extend(copy.deepcopy(values))
        return {'updates': {'updatedRange': f"'student_attachments'!A{start}:E{len(self.rows)}"}}


class StudentNotesTests(unittest.TestCase):
    def setUp(self):
        self.notes = NoteSheet([NOTE_HEADERS])
        self.files = NoteSheet([FILE_HEADERS])

    def test_text_only_is_persistent_idempotent_and_account_scoped(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Half bowl of pan mee')
        save_note(self.notes, None, prepared)
        self.assertEqual(save_note(self.notes, None, prepared), 'unchanged')
        self.assertEqual(load_notes(self.notes, 'bob'), [])
        self.assertEqual(load_notes(self.notes, 'alice', '2026-10-18'), [])
        restored = load_notes(self.notes, 'alice', '2026-10-19')[0]
        self.assertTrue(restored['needs_calories'])
        self.assertEqual(restored['Remarks'], 'Half bowl of pan mee')
        self.assertEqual(restored['files'], [])

    def test_files_roundtrip_and_do_not_become_public_urls(self):
        data = b'%PDF-1.7\n' + b'x' * 90000
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', '', [('folder/label.pdf', data)])
        save_note(self.notes, self.files, prepared)
        note = load_notes(self.notes, 'alice')[0]
        meta = note['files'][0]
        with patch.object(self.files, 'get_all_values', side_effect=AssertionError('Download must use a narrow range')):
            restored, verified = download_attachment(self.notes, self.files, 'alice', note['note_id'], meta['file_id'])
        self.assertEqual(restored, data)
        self.assertEqual(verified['name'], 'label.pdf')
        self.assertNotIn('url', verified)
        with self.assertRaises(ValueError):
            download_attachment(self.notes, self.files, 'bob', note['note_id'], meta['file_id'])

    def test_failed_file_write_does_not_commit_a_note(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Label', [('label.pdf', b'%PDF-1.7\ncontents')])
        with patch.object(self.files, 'append_rows', side_effect=ConnectionError('offline')):
            with self.assertRaises(ConnectionError):
                save_note(self.notes, self.files, prepared)
        self.assertEqual(load_notes(self.notes, 'alice'), [])
        save_note(self.notes, self.files, prepared)
        self.assertEqual(len(load_notes(self.notes, 'alice')), 1)

    def test_lost_note_ack_retry_keeps_one_manifest(self):
        prepared = prepare_note('alice', '2026-10-19', 'Snack', '=literal remark', needs_calories=False)
        append = self.notes.append_row
        def lost_ack(*args, **kwargs):
            append(*args, **kwargs)
            raise TimeoutError('lost')
        with patch.object(self.notes, 'append_row', side_effect=lost_ack):
            with self.assertRaises(TimeoutError):
                save_note(self.notes, None, prepared)
        self.assertEqual(save_note(self.notes, None, prepared), 'unchanged')
        self.assertEqual(len(self.notes.rows), 2)
        self.assertFalse(load_notes(self.notes, 'alice')[0]['needs_calories'])

    def test_invalid_and_oversized_files_rejected_before_storage(self):
        for uploads in ([('test.exe', b'MZbinary')], [('label.pdf', b'not a pdf')],
                        [('photo.jpg', b'\xff\xd8\xff' + b'x' * MAX_FILE_BYTES)],
                        [('label.pdf', b'%PDF-x')] * 3):
            with self.assertRaises(ValueError):
                prepare_note('alice', '2026-10-19', 'Lunch', 'Note', uploads)
        with self.assertRaises(ValueError):
            prepare_note('alice', '2026-10-19', 'Lunch', '')

    def test_corrupt_or_cross_account_chunks_never_download(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Note', [('label.pdf', b'%PDF-1.7\ncontent')])
        save_note(self.notes, self.files, prepared)
        note = load_notes(self.notes, 'alice')[0]
        self.files.rows[1][1] = 'bob'
        with self.assertRaises(ValueError):
            download_attachment(self.notes, self.files, 'alice', note['note_id'], note['files'][0]['file_id'])

    def test_unknown_schema_is_not_overwritten(self):
        self.notes.rows = [['wrong'], ['keep']]
        before = copy.deepcopy(self.notes.rows)
        with self.assertRaises(ValueError):
            save_note(self.notes, None, prepare_note('alice', '2026-10-19', 'Lunch', 'Note'))
        self.assertEqual(self.notes.rows, before)

    def test_mark_counted_retains_remarks_and_account_scope(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Pan mee')
        save_note(self.notes, None, prepared)
        with self.assertRaises(ValueError):
            mark_note_counted(self.notes, 'bob', prepared['note_id'])
        mark_note_counted(self.notes, 'alice', prepared['note_id'])
        restored = load_notes(self.notes, 'alice')[0]
        self.assertFalse(restored['needs_calories'])
        self.assertEqual(restored['Remarks'], 'Pan mee')

    def test_partial_day_status_never_becomes_complete_or_zero(self):
        records = [{'Date': '2026-10-19', 'Net_Calories': 75}, {'Date': '2026-10-18', 'Net_Calories': 50}]
        notes = [{'Date': '2026-10-19', 'needs_calories': True}]
        result = annotate_energy_status(records, notes)
        self.assertEqual(result[0]['Net_Calories'], 75)
        self.assertFalse(result[0]['Energy_complete'])
        self.assertEqual(result[0]['Pending_calorie_notes'], 1)
        self.assertTrue(result[1]['Energy_complete'])
        self.assertIsNone(annotate_energy_status(records, None)[0]['Energy_complete'])

    def test_attachment_commit_ack_loss_and_retry_do_not_duplicate_files(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Note', [('label.pdf', b'%PDF-1.7\\ncontent')])
        append = self.notes.append_row
        def lost_ack(*args, **kwargs):
            append(*args, **kwargs)
            raise TimeoutError('lost')
        with patch.object(self.notes, 'append_row', side_effect=lost_ack):
            with self.assertRaises(TimeoutError):
                save_note(self.notes, self.files, prepared)
        original_file_rows = copy.deepcopy(self.files.rows)
        self.assertEqual(save_note(self.notes, self.files, prepared), 'unchanged')
        self.assertEqual(self.files.rows, original_file_rows)

    def test_two_files_keep_separate_ranges_and_corrupt_metadata_fails_safely(self):
        prepared = prepare_note('alice', '2026-10-19', 'Lunch', 'Note',
                                [('first.pdf', b'%PDF-1.7\\nfirst'), ('second.pdf', b'%PDF-1.7\\nsecond')])
        save_note(self.notes, self.files, prepared)
        note = load_notes(self.notes, 'alice')[0]
        for meta, expected in zip(note['files'], [b'%PDF-1.7\\nfirst', b'%PDF-1.7\\nsecond']):
            data, _ = download_attachment(self.notes, self.files, 'alice', note['note_id'], meta['file_id'])
            self.assertEqual(data, expected)
        self.notes.rows[1][5] = '[{}]'
        with self.assertRaises(ValueError):
            load_notes(self.notes, 'alice')


if __name__ == '__main__':
    unittest.main()

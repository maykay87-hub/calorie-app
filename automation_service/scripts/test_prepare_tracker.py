import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import prepare_tracker as tracker


class PreparationTests(unittest.TestCase):
    def test_private_configuration_round_trip_and_isolation(self):
        key = {'type': 'service_account', 'client_email': 'synthetic@example.invalid',
               'client_x509_cert_url': 'https://example.invalid/synthetic',
               'private_key': '-----BEGIN PRIVATE KEY-----\nSYNTHETIC\n-----END PRIVATE KEY-----\n'}
        text = tracker.configuration('test-sheet', 'student-sheet', 'https://synthetic.run.app',
                                     'b' * 40, key, 'p' * 40)
        result = tomllib.loads(text)
        self.assertEqual(result['staging_spreadsheet_id'], 'test-sheet')
        self.assertEqual(result['service_account'], key)
        self.assertFalse(result['membership_service']['legacy_link_enabled'])
        self.assertTrue(result['membership_service']['enabled'])
        with self.assertRaises(tracker.SetupError):
            tracker.configuration('same', 'same', 'https://synthetic.run.app', 'b' * 40, key, 'p' * 40)

    def test_private_output_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private.toml'
            tracker.write_private(path, 'synthetic-secret')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), 'synthetic-secret')
            tracker.write_private(path, 'replacement')
            self.assertEqual(path.read_text(), 'replacement')
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_existing_secret_is_reused_without_creating_or_rotating(self):
        calls = []
        def fake(*args, **kw):
            calls.append(args)
            return '{}' if args[1] == 'describe' else 'synthetic-private-value'
        with patch.object(tracker, 'cloud', fake):
            result = tracker.private_secret('synthetic', 'private-key', lambda: self.fail('Unexpected rotation'))
        self.assertEqual(result, 'synthetic-private-value')
        self.assertFalse(any('create' in call for call in calls))

    def test_new_secret_is_sent_on_stdin(self):
        calls = []
        def fake(*args, **kw):
            calls.append((args, kw))
            return None if args[1] == 'describe' else '{}'
        with patch.object(tracker, 'cloud', fake):
            tracker.private_secret('synthetic', 'private-key', lambda: 'SYNTHETIC-PRIVATE')
        self.assertNotIn('SYNTHETIC-PRIVATE', str([args for args, _ in calls]))
        self.assertEqual(calls[-1][1]['data'], 'SYNTHETIC-PRIVATE')

    def test_errors_do_not_print_provider_diagnostics(self):
        class Result:
            returncode = 1
            stderr = 'PERMISSION_DENIED: SYNTHETIC-PRIVATE'
        with patch.object(tracker.subprocess, 'run', return_value=Result()):
            with self.assertRaises(tracker.SetupError) as error:
                tracker.cloud('example', missing=True)
        self.assertNotIn('SYNTHETIC-PRIVATE', str(error.exception))

    def test_safe_operation_and_error_categories(self):
        self.assertEqual(tracker.operation_name(('iam', 'service-accounts', 'keys', 'create', 'PRIVATE-PATH')),
                         'create staging Sheets key')
        for raw, expected in [
            ('PERMISSION_DENIED: private-value', 'PERMISSION_DENIED'),
            ('Please run gcloud auth login with PRIVATE-ACCOUNT', 'AUTHENTICATION_REQUIRED'),
            ('constraint iam.disableServiceAccountKeyCreation PRIVATE-ACCOUNT', 'KEY_CREATION_BLOCKED_BY_POLICY'),
            ('unrecognized arguments: PRIVATE-VALUE', 'CLI_ARGUMENT_ERROR'),
            ('private-provider-message', 'CLOUD_COMMAND_FAILED')]:
            self.assertEqual(tracker.error_category(raw), expected)

    def test_missing_cloud_run_service_is_not_a_permission_failure(self):
        class Result:
            returncode = 1
            stderr = 'ERROR: (gcloud.run.services.describe) Cannot find service [synthetic].'
        with patch.object(tracker.subprocess, 'run', return_value=Result()):
            self.assertIsNone(tracker.cloud('run', 'services', 'describe', 'synthetic', missing=True))
            with self.assertRaises(tracker.SetupError):
                tracker.cloud('run', 'services', 'describe', 'synthetic')


if __name__ == '__main__':
    unittest.main()

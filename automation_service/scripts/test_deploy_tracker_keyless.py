import tomllib
import unittest
from unittest.mock import patch
import deploy_tracker_keyless as deploy


class KeylessDeploymentTests(unittest.TestCase):
    def test_configuration_has_no_google_private_key(self):
        text = deploy.keyless_configuration('test-sheet', 'student-sheet', 'https://synthetic.run.app', 'b' * 40, 'p' * 40)
        value = tomllib.loads(text)
        self.assertTrue(value['google_sheets']['use_runtime_identity'])
        self.assertNotIn('service_account', value)
        self.assertNotIn('private_key', text)
        self.assertFalse(value['membership_service']['legacy_link_enabled'])
        self.assertEqual(value['staging_spreadsheet_id'], 'test-sheet')

    def test_refuses_student_sheet_or_shared_credentials(self):
        for test, student, bridge, password in [('same', 'same', 'b' * 40, 'p' * 40),
                                                ('test', 'student', 'b' * 40, 'b' * 40)]:
            with self.assertRaises(deploy.SetupError):
                deploy.keyless_configuration(test, student, 'https://synthetic.run.app', bridge, password)

    def test_deployment_limits_and_pinned_secret(self):
        args = deploy.deploy_arguments('synthetic', 'runtime@example.invalid', 'synthetic-image', 'private-config', '7')
        self.assertIn('--min-instances=0', args)
        self.assertIn('--max-instances=1', args)
        self.assertIn('--cpu-throttling', args)
        self.assertIn('--update-secrets=/app/.streamlit/secrets.toml=private-config:7', args)
        self.assertNotIn('latest', str(args))
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', str(args))
        self.assertNotIn('key', str(deploy.build_definition('synthetic-image')['steps'][0]['args']))

    def test_configuration_is_stored_over_stdin(self):
        calls = []
        def cloud(*args, **kw):
            calls.append((args, kw))
            return None if args[1] == 'describe' else '{}'
        with patch.object(deploy, 'cloud', cloud):
            name, version = deploy.store_configuration('synthetic', 'SYNTHETIC-PRIVATE')
        self.assertEqual(version, '1')
        self.assertNotIn('SYNTHETIC-PRIVATE', str([args for args, _ in calls]))
        self.assertEqual(calls[-1][1]['data'], 'SYNTHETIC-PRIVATE')


if __name__ == '__main__':
    unittest.main()

import unittest
from sheet_credentials import SCOPES, LEGACY_SCOPES, spreadsheet_credentials


class SheetCredentialsTests(unittest.TestCase):
    def test_keyless_scopes_and_runtime_identity(self):
        calls = []
        credentials = object()
        result = spreadsheet_credentials({'google_sheets': {'use_runtime_identity': True}}, 'staging',
            environ={'K_SERVICE': 'synthetic-test'}, adc=lambda **kw: calls.append(kw) or (credentials, 'synthetic'))
        self.assertIs(result, credentials)
        self.assertEqual(calls, [{'scopes': SCOPES}])

    def test_production_or_community_cloud_cannot_enable_keyless_mode(self):
        for environment, variables in [('production', {'K_SERVICE': 'synthetic'}), ('staging', {})]:
            with self.assertRaises(ValueError):
                spreadsheet_credentials({'google_sheets': {'use_runtime_identity': True}}, environment,
                    environ=variables, adc=lambda **kw: self.fail('Unexpected ADC request'))

    def test_external_key_file_is_rejected_in_keyless_mode(self):
        with self.assertRaises(ValueError):
            spreadsheet_credentials({'google_sheets': {'use_runtime_identity': True}}, 'staging',
                environ={'K_SERVICE': 'synthetic', 'GOOGLE_APPLICATION_CREDENTIALS': 'synthetic-private-path'},
                adc=lambda **kw: self.fail('Unexpected ADC request'))

    def test_existing_production_service_account_path_remains_available(self):
        credential = {'type': 'synthetic', 'private_key': 'synthetic'}
        calls = []
        result = spreadsheet_credentials({'service_account': credential}, 'production', environ={},
            service_account=lambda value, scopes: calls.append((value, scopes)) or 'synthetic-credentials')
        self.assertEqual(result, 'synthetic-credentials')
        self.assertEqual(calls, [(credential, LEGACY_SCOPES)])

    def test_string_true_does_not_activate_runtime_identity(self):
        result = spreadsheet_credentials({'google_sheets': {'use_runtime_identity': 'true'}, 'service_account': {}},
            'staging', environ={}, service_account=lambda *_: 'legacy')
        self.assertEqual(result, 'legacy')


if __name__ == '__main__':
    unittest.main()

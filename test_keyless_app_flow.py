"""Keyless staging login with a fake Sheet, short-lived identity and member bridge."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_app_flow import AppFlowTests
from sheet_credentials import SCOPES


class KeylessAppFlowTests(unittest.TestCase):
    def test_managed_login_without_a_service_account_key(self):
        fixture = AppFlowTests('test_login_form_rejects_wrong_password_then_clears_successful_credentials')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        app = AppTest.from_file(str(Path(__file__).with_name('staging.app.py')), default_timeout=15)
        app.secrets.update({
            'staging_spreadsheet_id': 'synthetic-independent-test',
            'production_spreadsheet_id': 'synthetic-student-guard',
            'passwords': {},
            'google_sheets': {'use_runtime_identity': True},
            'membership_service': {'enabled': True, 'legacy_link_enabled': False,
                                   'url': 'https://members.example.invalid', 'bridge_key': 'b' * 40},
        })
        managed = {'username': 'mb_' + 'c' * 32, 'display_name': 'Synthetic Member',
                   'token': 't' * 43, 'active': True, 'ends_at': 4102444800}
        with patch.dict(os.environ, {'K_SERVICE': 'synthetic-keyless-test'}), \
             patch('google.auth.default', return_value=(object(), 'synthetic')) as identity, \
             patch('member_access.login', return_value=managed):
            app.run()
            self.assertFalse(app.exception)
            app.text_input(key='login_user').set_value('synthetic@example.invalid')
            app.text_input(key='login_pass').set_value('Synthetic-password-123!')
            app.button(key='login_btn').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['username'], managed['username'])
            identity.assert_called_once_with(scopes=SCOPES)
            self.assertEqual(app.session_state['sheet_connection']['id'], 'synthetic-independent-test')


if __name__ == '__main__':
    unittest.main()

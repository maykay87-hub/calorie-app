"""Optional keyless credentials for a dedicated Cloud Run staging identity."""
import os

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
LEGACY_SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']


def spreadsheet_credentials(secrets, environment, *, environ=None, adc=None, service_account=None):
    environ = os.environ if environ is None else environ
    keyless = secrets.get('google_sheets', {}).get('use_runtime_identity') is True
    if keyless:
        if environment != 'staging' or not environ.get('K_SERVICE'):
            raise ValueError('Keyless Sheets access requires the dedicated Cloud Run staging deployment.')
        if environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            raise ValueError('Keyless staging must use its attached runtime identity, not a key file.')
        if adc is None:
            import google.auth
            adc = google.auth.default
        return adc(scopes=SCOPES)[0]
    if service_account is None:
        from oauth2client.service_account import ServiceAccountCredentials
        service_account = ServiceAccountCredentials.from_json_keyfile_dict
    return service_account(dict(secrets['service_account']), LEGACY_SCOPES)

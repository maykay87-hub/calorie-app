import json
from cryptography.fernet import Fernet
from .config import PLANS
from .preflight import inspect_environment, REQUIRED

def configured():
    return dict(MB_ENV='production',MB_DATABASE_URL='postgresql+psycopg://member:secret@db.invalid/members_test',
        MB_ENCRYPTION_KEY=Fernet.generate_key().decode(),MB_ADMIN_KEY='a'*40,MB_BRIDGE_KEY='b'*40,
        STRIPE_WEBHOOK_SECRET='whsec_'+'w'*40,STRIPE_SECRET_KEY='sk_test_synthetic',
        MB_PUBLIC_URL='https://members.example.invalid',MB_TRACKER_URL='https://may-bloom-lab.streamlit.app/',
        MB_BILLING_PORTAL_URL='https://billing.stripe.com/p/login/synthetic',
        MB_STRIPE_PRICE_PLANS=json.dumps({'price_'+str(i):p for i,p in enumerate(PLANS)}),
        MB_SMTP_HOST='smtp.example.invalid',MB_SMTP_USER='sender',MB_SMTP_PASSWORD='mail-secret-synthetic',
        MB_MAIL_FROM='hello@example.invalid',MB_COACH_EMAIL='coach@example.invalid')

def test_valid_offline_setup_does_not_claim_external_connections():
    result=inspect_environment(configured())
    assert result['configuration_valid'] and not result['external_connections_checked']

def test_missing_settings_report_names_without_values():
    result=inspect_environment({})
    assert not result['configuration_valid']
    assert set(REQUIRED)<=set(p['field'] for p in result['problems'])

def test_wrong_modes_bad_mapping_and_secret_redaction():
    env=configured();env.update(MB_STRIPE_LIVE='true',MB_PUBLIC_URL='https://user:sensitive@invalid/',MB_STRIPE_PRICE_PLANS='["sensitive"]')
    result=inspect_environment(env);output=json.dumps(result)
    assert {'MB_RELEASE_REVIEWED','STRIPE_SECRET_KEY','MB_PUBLIC_URL','MB_STRIPE_PRICE_PLANS'}<=set(p['field'] for p in result['problems'])
    assert 'sensitive' not in output and env['MB_ENCRYPTION_KEY'] not in output

def test_wrong_database_driver_caught_before_runtime_connect():
    env=configured();env['MB_DATABASE_URL']='postgresql://member:secret@db.invalid/test'
    assert any(p['field']=='MB_DATABASE_URL' for p in inspect_environment(env)['problems'])

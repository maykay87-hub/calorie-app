"""Offline deployment checks. Output contains field names only, never secret values."""
import json
import os
import re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url
from .config import PLANS
from .security import email_key

REQUIRED = ('MB_DATABASE_URL','MB_ENCRYPTION_KEY','MB_ADMIN_KEY','MB_BRIDGE_KEY',
            'MB_PUBLIC_URL','MB_TRACKER_URL','MB_BILLING_PORTAL_URL','STRIPE_SECRET_KEY',
            'STRIPE_WEBHOOK_SECRET','MB_STRIPE_PRICE_PLANS','MB_SMTP_HOST','MB_SMTP_USER',
            'MB_SMTP_PASSWORD','MB_MAIL_FROM','MB_COACH_EMAIL')

def inspect_environment(env):
    problems=[]
    def fail(field,reason): problems.append({'field':field,'reason':reason})
    for name in REQUIRED:
        if not env.get(name,'').strip(): fail(name,'missing')
    if env.get('MB_ENV')!='production': fail('MB_ENV','must_be_production_for_hosted_service')
    for name in ('MB_STRIPE_LIVE','MB_RELEASE_REVIEWED','MB_BOOKING_ENABLED','MB_LEGACY_LINK_ENABLED','MB_RENEWAL_ENABLED'):
        if env.get(name,'false') not in ('true','false'): fail(name,'must_be_true_or_false')
    live=env.get('MB_STRIPE_LIVE')=='true'
    if live and env.get('MB_RELEASE_REVIEWED')!='true': fail('MB_RELEASE_REVIEWED','live_release_not_reviewed')
    key=env.get('STRIPE_SECRET_KEY','')
    if key and not key.startswith('sk_live_' if live else 'sk_test_'): fail('STRIPE_SECRET_KEY','mode_or_key_type_mismatch')
    if env.get('STRIPE_WEBHOOK_SECRET') and not env['STRIPE_WEBHOOK_SECRET'].startswith('whsec_'):
        fail('STRIPE_WEBHOOK_SECRET','invalid_prefix')
    secrets=[env.get(n,'') for n in ('MB_ADMIN_KEY','MB_BRIDGE_KEY','STRIPE_WEBHOOK_SECRET')]
    if any(v and len(v)<32 for v in secrets): fail('SERVER_KEYS','minimum_32_characters')
    if len(set(secrets))!=len(secrets): fail('SERVER_KEYS','must_be_distinct')
    if env.get('MB_ENCRYPTION_KEY'):
        try: Fernet(env['MB_ENCRYPTION_KEY'].encode())
        except (ValueError,TypeError): fail('MB_ENCRYPTION_KEY','invalid_fernet_key')
    for name in ('MB_PUBLIC_URL','MB_TRACKER_URL','MB_BILLING_PORTAL_URL'):
        value=env.get(name,'')
        if not value: continue
        try:
            url=urlsplit(value)
            valid=url.scheme=='https' and bool(url.hostname) and not url.username and not url.password and not url.fragment
            if name=='MB_PUBLIC_URL': valid=valid and url.path in ('','/') and not url.query and url.port in (None,443)
            if name=='MB_TRACKER_URL': valid=valid and url.hostname in ('maybloom-lifestyle-tracker.streamlit.app','may-bloom-lab.streamlit.app') and not url.query
            if name=='MB_BILLING_PORTAL_URL': valid=valid and url.hostname=='billing.stripe.com' and url.path.startswith('/p/login/')
            if not valid: fail(name,'invalid_service_url')
        except ValueError: fail(name,'invalid_service_url')
    if env.get('MB_DATABASE_URL'):
        try:
            db=make_url(env['MB_DATABASE_URL'])
            if db.drivername!='postgresql+psycopg' or not db.database:
                fail('MB_DATABASE_URL','use_postgresql_psycopg_and_dedicated_database')
        except Exception: fail('MB_DATABASE_URL','invalid_database_url')
    if env.get('MB_STRIPE_PRICE_PLANS'):
        try:
            prices=json.loads(env['MB_STRIPE_PRICE_PLANS'])
            if not isinstance(prices,dict) or len(prices)!=4 or set(prices.values())!=set(PLANS) or not all(k.startswith('price_') for k in prices):
                fail('MB_STRIPE_PRICE_PLANS','four_exact_price_mappings_required')
        except (ValueError,TypeError): fail('MB_STRIPE_PRICE_PLANS','invalid_price_mapping')
    for name in ('MB_MAIL_FROM','MB_COACH_EMAIL'):
        if env.get(name):
            try: email_key(env[name])
            except ValueError: fail(name,'use_plain_valid_email')
    for name,default,low,high in (('MB_SMTP_PORT','587',1,65535),('MB_BOOKING_LEAD_SECONDS','86400',0,31536000)):
        try:
            if not low<=int(env.get(name,default))<=high: raise ValueError()
        except ValueError: fail(name,'invalid_integer_range')
    if env.get('MB_PACKAGE_START','activation') not in ('activation','payment'): fail('MB_PACKAGE_START','invalid_start_policy')
    if env.get('MB_TASK_QUEUE') and not re.fullmatch(r'projects/[a-zA-Z0-9_-]+/locations/[a-z0-9-]+/queues/[a-zA-Z0-9_-]+', env['MB_TASK_QUEUE']):
        fail('MB_TASK_QUEUE','use_cloud_tasks_queue_resource_path')
    return {'configuration_valid':not problems,'mode':'live' if live else 'test',
            'problems':problems,'external_connections_checked':False,
            'note':'Offline configuration only. Stripe prices/webhook, PostgreSQL, SMTP inbox and scheduled delivery still require end-to-end verification.'}

def main():
    result=inspect_environment(os.environ)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['configuration_valid'] else 2

if __name__=='__main__': raise SystemExit(main())

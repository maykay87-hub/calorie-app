"""Synthetic-only integration and concurrency tests. Never call live Stripe or SMTP."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import hmac
import json
from types import SimpleNamespace
import time
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest
from .app import create_app
from .config import Settings
from .service import Service, RuleError, add_months
from .store import Store, accounts, grants, events, outbox, bookings, one, rows
from .stripe_gateway import StripeGateway

NOW=1792627200
PASSWORD='Testing-members-123!'

@pytest.fixture
def setup(tmp_path):
    settings=Settings(database_url='sqlite:///'+str(tmp_path/'members.sqlite'),
        encryption_key=Fernet.generate_key().decode(),admin_key='a'*40,bridge_key='b'*40,
        webhook_secret='whsec_'+'s'*40,booking_enabled=True,legacy_link_enabled=True,price_plans={'price_test_monthly':'tracker-monthly'},
        tracker_url='https://example.invalid/tracker')
    clock=[NOW]; service=Service(Store(settings.database_url),settings,clock=lambda:clock[0])
    return service,settings,clock

def purchase(email='student@example.invalid',plan='consultation-initial',source='cs:one',customer=None,paid_at=NOW):
    return {'source_id':source,'plan':plan,'email':email,'customer_id':customer,'paid_at':paid_at}

def activate(service,email='student@example.invalid'):
    with service.store.read() as c:
        for msg in rows(c,outbox):
            payload=json.loads(service.cipher.decrypt(msg['payload'].encode()))
            if payload['kind']=='activation' and payload['to']==email:
                token=payload['body'].split('#activate=')[1].split()[0]
    return service.activate(token,PASSWORD)

def member(service,**kw):
    service.fulfill('evt_'+kw.get('source','cs:one'),'checkout.session.completed',purchase(**kw))
    return activate(service,kw.get('email','student@example.invalid'))

def test_paid_purchase_activation_and_single_use(setup):
    s,_,_=setup;s.fulfill('evt_a','checkout.session.completed',purchase())
    token=activate(s);me=s.me(token)
    assert me['active'] and me['credits']==1 and me['ends_at']==NOW+7*86400
    with pytest.raises(RuleError): activate(s)
    assert s.me(s.login('STUDENT@example.invalid',PASSWORD))['username']==me['username']

def test_duplicate_events_and_different_events_same_checkout_do_not_extend(setup):
    s,_,clock=setup;token=member(s)
    before=s.me(token);clock[0]+=60
    assert s.fulfill('evt_cs:one','checkout.session.completed',purchase())=='duplicate'
    s.fulfill('evt_another','checkout.session.async_payment_succeeded',purchase())
    assert s.me(token)['ends_at']==before['ends_at'] and s.me(token)['credits']==1
    with s.store.read() as c: assert len(rows(c,grants))==1

def test_periods_use_calendar_months_and_initial_package_waits_for_activation(setup):
    jan31=int(datetime(2028,1,31,12,tzinfo=timezone.utc).timestamp())
    assert datetime.fromtimestamp(add_months(jan31,1),timezone.utc).day==29
    s,_,clock=setup;s.fulfill('evt_a','checkout.session.completed',purchase(plan='consultation-three-months'))
    clock[0]+=86400
    s.request_activation('student@example.invalid')
    token=activate(s)
    assert s.me(token)['ends_at']==add_months(clock[0],3)

def test_existing_member_keeps_identity_and_records_key_on_new_purchase(setup):
    s,_,_=setup;token=member(s);username=s.me(token)['username']
    s.fulfill('evt_two','checkout.session.completed',purchase(source='cs:two',plan='consultation-three-months'))
    assert s.me(token)['username']==username and s.me(token)['credits']==4
    with s.store.read() as c: assert len(rows(c,accounts))==1

def test_legacy_link_requires_unspent_tracker_identity_and_blocks_reserved_name(setup):
    s,_,_=setup;token=member(s)
    assert s.link_legacy(token,'original-student')=='original-student'
    assert s.me(token)['username']=='original-student'
    assert s.legacy_login('unmapped-student')=={'managed':False}
    assert s.legacy_login('original-student')['active']
    with pytest.raises(RuleError): s.link_legacy(token,'admin')
    with pytest.raises(RuleError): s.link_legacy(token,'other-account')

def test_used_new_tracker_account_cannot_be_renamed_over_old_data(setup):
    s,_,_=setup;token=member(s);before=s.tracker_session(token)['username']
    with pytest.raises(RuleError): s.link_legacy(token,'old-name')
    assert s.me(token)['username']==before

def test_account_isolation_and_password_reset_revokes_previous_sessions(setup):
    s,_,_=setup;a=member(s);b=member(s,email='other@example.invalid',source='cs:two')
    assert s.me(a)['username']!=s.me(b)['username']
    s.request_activation('student@example.invalid');replacement=activate(s)
    with pytest.raises(RuleError): s.me(a)
    assert s.me(replacement)['credits']==1 and s.me(b)['credits']==1

def test_login_rate_limit_survives_failed_passwords(setup):
    s,_,_=setup;member(s)
    for _ in range(8):
        with pytest.raises(RuleError) as e: s.login('student@example.invalid','wrong')
        assert e.value.status==401
    with pytest.raises(RuleError) as e: s.login('student@example.invalid',PASSWORD)
    assert e.value.status==429

def test_monthly_renewal_uses_paid_invoice_period_not_event_arrival(setup):
    s,_,_=setup
    data=purchase(plan='tracker-monthly',source='in:first',customer='cus_one')
    data.update(subscription_id='sub_one',starts_at=NOW,ends_at=NOW+30*86400)
    s.fulfill('evt_one','invoice.paid',data);token=activate(s)
    renewal=dict(data,source_id='in:second',starts_at=NOW+30*86400,ends_at=NOW+61*86400)
    s.fulfill('evt_two','invoice.paid',renewal)
    assert s.me(token)['ends_at']==NOW+30*86400 # next period has not started
    s.fulfill('evt_late','invoice.paid',data)
    with s.store.read() as c: assert len(rows(c,grants))==2

def test_failed_payment_retains_paid_access_and_ended_subscription_respects_other_package(setup):
    s,_,_=setup;data=purchase(plan='tracker-monthly',source='in:one')
    data.update(subscription_id='sub_one',starts_at=NOW,ends_at=NOW+30*86400)
    s.fulfill('evt_paid','invoice.paid',data);token=activate(s)
    s.flag('evt_failed','invoice.payment_failed');assert s.me(token)['active']
    s.reconcile_subscription('evt_end','customer.subscription.deleted',{'id':'sub_one','cap_at':NOW,'event_time':NOW})
    assert not s.me(token)['active']
    s.fulfill('evt_package','checkout.session.completed',purchase(source='cs:package'))
    assert s.me(token)['active']

def test_stale_subscription_update_does_not_reopen_ended_access(setup):
    s,_,_=setup
    s.reconcile_subscription('evt_new','customer.subscription.deleted',{'id':'sub_one','cap_at':NOW,'event_time':NOW})
    s.reconcile_subscription('evt_old','customer.subscription.updated',{'id':'sub_one','cap_at':None,'event_time':NOW-100})
    with s.store.read() as c:
        from .store import subscriptions
        assert one(c,subscriptions,subscriptions.c.id=='sub_one')['cap_at']==NOW

def test_booking_consumes_one_credit_retry_is_idempotent_and_no_oversell(setup):
    s,_,_=setup;token=member(s);sid=s.publish_slot(NOW+2*86400)
    bid=s.book(token,sid,'request-123')
    assert s.book(token,sid,'request-123')==bid and s.me(token)['credits']==0
    with pytest.raises(RuleError): s.book(token,sid,'request-456')
    with s.store.read() as c: assert len(rows(c,bookings))==1

def test_two_members_racing_for_one_slot_only_one_wins(setup):
    s,_,_=setup;a=member(s);b=member(s,email='other@example.invalid',source='cs:two');sid=s.publish_slot(NOW+2*86400)
    def attempt(token):
        try: return s.book(token,sid,'request-concurrent')
        except RuleError: return None
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(attempt,[a,b]))
    assert sum(r is not None for r in results)==1
    assert sorted([s.me(a)['credits'],s.me(b)['credits']])==[0,1]

def test_one_credit_racing_for_two_slots_only_one_wins(setup):
    s,_,_=setup;token=member(s);ids=[s.publish_slot(NOW+i*86400) for i in [2,3]]
    def attempt(sid):
        try: return s.book(token,sid,'request-'+sid)
        except RuleError: return None
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(attempt,ids))
    assert sum(r is not None for r in results)==1

def test_slot_buffer_expiry_and_closed_booking_are_enforced(setup):
    s,settings,clock=setup;token=member(s);sid=s.publish_slot(NOW+2*86400)
    with pytest.raises(RuleError): s.publish_slot(NOW+2*86400+3000)
    far=s.publish_slot(NOW+9*86400)
    with pytest.raises(RuleError): s.book(token,far,'request-expired')
    settings.booking_enabled=False
    with pytest.raises(RuleError): s.book(token,sid,'request-disabled')
    settings.booking_enabled=True;clock[0]+=8*86400
    fresh=s.login('student@example.invalid',PASSWORD)
    assert not s.me(fresh)['active']

def test_outbox_encrypts_activation_and_delivery_failures_are_visible(setup):
    s,_,_=setup;member(s)
    with s.store.read() as c:
        assert all('activate=' not in msg['payload'] and 'student@' not in msg['payload'] for msg in rows(c,outbox))
    def fail(*args): raise TimeoutError()
    assert s.deliver_pending(fail)==0
    summary=s.admin_summary()
    assert summary['issues'] and all(m['status']=='uncertain' for m in summary['mail'])
    assert s.deliver_pending(lambda *_:pytest.fail('Uncertain emails must not be blindly resent'))==0

def test_reminder_runs_once_and_mail_sender_only_runs_from_jobs(setup):
    s,_,clock=setup;token=member(s);sid=s.publish_slot(NOW+2*86400);s.book(token,sid,'request-once')
    clock[0]+=86400;s.enqueue_reminders();s.enqueue_reminders();sent=[]
    s.deliver_pending(lambda key,payload:sent.append((key,payload)))
    assert sum(p['kind']=='reminder' for _,p in sent)==1
    assert s.deliver_pending(lambda *_:pytest.fail('Already-sent mail repeated'))==0

def signed(event,settings):
    raw=json.dumps(event).encode();stamp=int(time.time())
    sig=hmac.new(settings.webhook_secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return raw,{'stripe-signature':f't={stamp},v1={sig}'}

def test_http_signed_webhook_activation_login_booking_and_csrf(setup):
    s,settings,clock=setup
    gateway=SimpleNamespace(checkout=lambda sid,at:purchase(),invoice=lambda iid,at:None)
    app=create_app(settings,s.store,gateway=gateway,sender=lambda *_:None,clock=lambda:clock[0])
    with TestClient(app,base_url=settings.public_url) as client:
        event={'id':'evt_http','created':NOW,'livemode':False,'type':'checkout.session.completed','data':{'object':{'id':'cs_paid'}}}
        raw,headers=signed(event,settings)
        assert client.post('/stripe/webhook',content=raw,headers=headers).status_code==200
        assert client.post('/stripe/webhook',content=raw+b' ',headers=headers).status_code==400
        assert client.get('/admin/summary').status_code==401
        assert client.post('/bridge/legacy-login',json={'username':'old'}).status_code==401
        assert client.post('/api/login',json={'email':'a@b.com','password':'x'}).status_code==403
        token=activate(s)
        login_response=client.post('/api/login',json={'email':'student@example.invalid','password':PASSWORD},headers={'origin':settings.public_url})
        assert login_response.status_code==200
        assert client.get('/api/me').json()['active']
        sid=s.publish_slot(NOW+2*86400)
        response=client.post('/api/book',json={'slot_id':sid,'request_id':'http-booking'},headers={'origin':settings.public_url})
        assert response.status_code==200
        assert client.get('/api/me').json()['credits']==0
        assert 'HttpOnly' in login_response.headers['set-cookie'] and 'SameSite=strict' in login_response.headers['set-cookie']
        assert client.get('/').headers['content-security-policy'].startswith("default-src 'self'")

def test_provider_error_is_retryable_and_mode_mismatch_rejected(setup):
    s,settings,clock=setup
    def fail(*_): raise ConnectionError('Do not return this provider diagnostic')
    app=create_app(settings,s.store,gateway=SimpleNamespace(checkout=fail),clock=lambda:clock[0])
    with TestClient(app) as client:
        event={'id':'evt_failure','created':NOW,'livemode':False,'type':'checkout.session.completed','data':{'object':{'id':'cs_one'}}}
        raw,headers=signed(event,settings);response=client.post('/stripe/webhook',content=raw,headers=headers)
        assert response.status_code==503 and 'diagnostic' not in response.text
        with s.store.read() as c: assert not one(c,events,events.c.id=='evt_failure')
        event['livemode']=True;raw,headers=signed(event,settings)
        assert client.post('/stripe/webhook',content=raw,headers=headers).status_code==400

def test_production_fails_closed_without_durable_database_and_release_review(setup):
    _,settings,_=setup;settings.production=True
    with pytest.raises(ValueError): settings.validate()
    settings.database_url='postgresql+psycopg://placeholder';settings.public_url='https://members.example.invalid';settings.live=True
    with pytest.raises(ValueError): settings.validate()

def test_gateway_uses_canonical_payment_not_untrusted_event_fields(setup):
    _,settings,_=setup;settings.price_plans={'price_package':'consultation-initial'}
    gateway=object.__new__(StripeGateway);gateway.settings=settings
    session={'livemode':False,'status':'complete','payment_status':'paid','mode':'payment','amount_total':19900,
             'customer_details':{'email':'real@example.invalid'},'line_items':{'data':[{'quantity':1,'price':{'id':'price_package'}}]}}
    gateway.client=SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=lambda *_:session)),
        prices=SimpleNamespace(retrieve=lambda _:dict(livemode=False,currency='myr',unit_amount=19900,recurring=None))))
    assert gateway.checkout('cs_canonical',NOW)['email']=='real@example.invalid'
    session['payment_status']='unpaid';assert gateway.checkout('cs_canonical',NOW) is None
    session['payment_status']='paid';session['line_items']['data'][0]['quantity']=2
    with pytest.raises(ValueError): gateway.checkout('cs_canonical',NOW)

def test_invoice_and_checkout_notifications_share_one_paid_monthly_grant(setup):
    s,settings,_=setup;gateway=object.__new__(StripeGateway);gateway.settings=settings
    class Resource:
        def __init__(self,data): self.data=data
        def to_dict(self): return self.data
    inv=Resource({'livemode':False,'status':'paid','amount_paid':4800,'customer':'cus_member',
                  'parent':{'subscription_details':{'subscription':'sub_member'}},'status_transitions':{'paid_at':NOW}})
    line={'pricing':{'price_details':{'price':'price_test_monthly'}},'quantity':1,
          'parent':{'subscription_item_details':{'proration':False}},'period':{'start':NOW,'end':NOW+30*86400}}
    line_response=Resource({'data':[line],'has_more':False})
    gateway.client=SimpleNamespace(v1=SimpleNamespace(
        invoices=SimpleNamespace(retrieve=lambda _:inv,line_items=SimpleNamespace(list=lambda *_:line_response)),
        subscriptions=SimpleNamespace(retrieve=lambda _:Resource({'livemode':False,'status':'active'})),
        prices=SimpleNamespace(retrieve=lambda _:Resource({'livemode':False,'currency':'myr','unit_amount':4800,
                                                          'recurring':{'interval':'month','interval_count':1}})),
        customers=SimpleNamespace(retrieve=lambda _:Resource({'email':'student@example.invalid'})),
        checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=lambda *_:Resource({'livemode':False,'status':'complete',
                                        'payment_status':'paid','mode':'subscription','invoice':'in_first'})))))
    s.fulfill('evt_checkout','checkout.session.completed',gateway.checkout('cs_subscription',NOW))
    s.fulfill('evt_invoice','invoice.paid',gateway.invoice('in_first',NOW))
    with s.store.read() as c: assert len(rows(c,grants))==1
    assert s.me(activate(s))['active']
    line['parent']['subscription_item_details']['proration']=True
    assert gateway.invoice('in_proration',NOW) is None

def test_fulfillment_failure_rolls_back_before_retry(setup,monkeypatch):
    s,_,_=setup
    original=s._queue
    def fail(*_): raise OSError('simulated durable write failure')
    monkeypatch.setattr(s,'_queue',fail)
    with pytest.raises(OSError): s.fulfill('evt_atomic','checkout.session.completed',purchase())
    with s.store.read() as c:
        assert not rows(c,accounts) and not rows(c,grants) and not rows(c,events)
    monkeypatch.setattr(s,'_queue',original)
    assert s.fulfill('evt_atomic','checkout.session.completed',purchase())=='processed'

def test_booking_notifies_coach_and_contains_malaysia_time(setup):
    s,settings,_=setup;settings.coach_email='coach@example.invalid';token=member(s)
    s.book(token,s.publish_slot(NOW+2*86400),'notify-coach')
    sent=[];s.deliver_pending(lambda key,payload:sent.append(payload))
    coach=next(p for p in sent if p['kind']=='coach_booking')
    student=next(p for p in sent if p['kind']=='booking')
    assert coach['to']=='coach@example.invalid' and 'MYT' in coach['body'] and 'MYT' in student['body']
    assert coach['booking_id']==student['booking_id']

def test_operator_can_close_empty_slot_but_cannot_silently_cancel_booking(setup):
    s,_,_=setup;token=member(s)
    sid=s.publish_slot(NOW+2*86400);s.close_slot(sid)
    assert s.available_slots(token)==[]
    assert s.publish_slot(NOW+2*86400)==sid
    s.book(token,sid,'operator-close-test')
    with pytest.raises(RuleError): s.close_slot(sid)

def test_expired_membership_cannot_replace_legacy_account_binding(setup):
    s,_,clock=setup;old=member(s);clock[0]+=8*86400
    token=s.login('student@example.invalid',PASSWORD)
    with pytest.raises(RuleError): s.link_legacy(token,'original-student')
    assert s.me(token)['username'].startswith('mb_')

def test_coach_email_requires_verification_and_other_members_cannot_manage_slots(setup):
    s,settings,_=setup;settings.coach_email='coach@example.invalid'
    s.request_activation('coach@example.invalid');coach=activate(s,'coach@example.invalid')
    assert s.me(coach)['is_coach'] and not s.me(coach)['active']
    s.coach_authorized(coach)
    student=member(s)
    assert not s.me(student)['is_coach']
    with pytest.raises(RuleError) as err: s.coach_authorized(student)
    assert err.value.status==403

"""Synthetic checkout, concurrency, intake and HTTP boundary tests; no provider calls."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from types import SimpleNamespace
import json
import hashlib
import hmac
import time as system_time
import pytest
from fastapi.testclient import TestClient
from .test_service import setup, activate, member, PASSWORD
from .availability import candidate_slots
from .app import create_app
from .consultation_checkout import ConsultationCheckout
from .intake import IntakeService, IntakeSubmission
from .service import RuleError
from .store import consultation_holds as holds, slots, bookings, grants, intakes, outbox, issues, rows, one
from .stripe_gateway import StripeGateway


class FakeGateway:
    def __init__(self): self.sessions={};self.lock=Lock();self.fail=False
    def consultation_checkout(self,context):
        if self.fail: raise OSError('provider timeout')
        with self.lock:
            self.sessions.setdefault(context['id'],dict(id='cs_'+context['id'],
                hold_id=context['id'],url='https://checkout.stripe.com/c/pay/test',
                expires_at=context['expires_at'],status='open'))
            return self.sessions[context['id']]
    def consultation_state(self,sid):
        return next(dict(value) for value in self.sessions.values() if value['id']==sid)


@pytest.fixture
def flow(setup):
    s,settings,clock=setup
    settings.consultation_checkout_enabled=True;settings.intake_enabled=True
    settings.intake_privacy_url='https://example.invalid/privacy';settings.intake_consent_version='test-v1'
    settings.coach_email='coach@example.invalid';settings.validate()
    gateway=FakeGateway();checkout=ConsultationCheckout(s,gateway)
    first=int(candidate_slots()[0][0].timestamp());slot_id=s.publish_slot(first)
    return s,settings,clock,gateway,checkout,slot_id


def reserve(flow,owner='browser-owner-token-000000000000',request='request-00000001',email='student@example.invalid',plan='consultation-initial'):
    s,settings,clock,gateway,checkout,sid=flow
    result=checkout.checkout(owner,email,plan,sid,request)
    with s.store.read() as c: hold=dict(one(c,holds,holds.c.id==result['hold_id']))
    return hold


def paid(s,hold,event='evt_paid',email=None):
    payload=dict(source_id='cs:'+hold['checkout_id'],plan=hold['plan'],email=email or hold['email'],
                 paid_at=s.now(),hold_id=hold['id'],customer_id=None)
    s.fulfill(event,'checkout.session.completed',payload)
    return payload


def test_enabled_slots_reservation_paid_booking_and_replay(flow):
    s,_,_,_,checkout,sid=flow
    assert checkout.available()['slots'][0]['id']==sid
    hold=reserve(flow)
    assert not checkout.available()['slots']
    with s.store.read() as c:
        assert not rows(c,bookings) and not rows(c,grants)
    payload=paid(s,hold)
    s.fulfill('evt_replay','checkout.session.completed',payload)
    token=activate(s)
    assert s.me(token)['credits']==0
    assert len(s.me(token)['appointments'])==1
    assert checkout.status('browser-owner-token-000000000000')['status']=='booked'
    assert checkout.status('a-different-browser')['status']=='none'
    with s.store.read() as c:
        assert len(rows(c,bookings))==len(rows(c,grants))==1
        messages=[json.loads(s.cipher.decrypt(row['payload'].encode())) for row in rows(c,outbox)]
        assert sum(message['kind']=='booking' for message in messages)==1
        assert '/intake' in next(message['body'] for message in messages if message['kind']=='booking')


def test_three_months_first_booking_consumes_one_credit(flow):
    s,*_=flow;hold=reserve(flow,plan='consultation-three-months');paid(s,hold)
    assert s.me(activate(s))['credits']==2


def test_two_buyers_cannot_reserve_same_slot(flow):
    def attempt(index):
        try: reserve(flow,owner='owner-'+str(index)*30,email=f'student{index}@example.invalid');return True
        except RuleError: return False
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(attempt,[1,2]))
    assert sum(result)==1
    with flow[0].store.read() as c: assert len(rows(c,holds))==1


def test_same_request_concurrency_uses_one_checkout(flow):
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(lambda _:reserve(flow),range(2)))
    assert result[0]['id']==result[1]['id']
    assert len(flow[3].sessions)==1


def test_hold_is_not_released_by_elapsed_clock_or_close_or_legacy_booking(flow):
    s,_,clock,gateway,checkout,sid=flow
    token=member(s,email='existing@example.invalid',source='cs:existing')
    hold=reserve(flow)
    with pytest.raises(RuleError): s.close_slot(sid)
    with pytest.raises(RuleError): s.book(token,sid,'legacy-attempt')
    clock[0]=hold['expires_at']+1;checkout.sweep()
    assert not checkout.available()['slots']
    gateway.sessions[hold['id']]['status']='expired';checkout.sweep()
    assert checkout.available()['slots'][0]['id']==sid


def test_unknown_provider_timeout_keeps_slot_and_retry_recovers(flow):
    s,_,clock,gateway,checkout,_=flow;gateway.fail=True
    with pytest.raises(OSError): reserve(flow)
    gateway.fail=False;hold=reserve(flow)
    assert hold['checkout_id']
    # An unknown result at a different slot stays blocked for operator review.
    second=int(candidate_slots()[1][0].timestamp());sid=s.publish_slot(second)
    gateway.fail=True
    with pytest.raises(OSError): checkout.checkout('different-owner','second@example.invalid','consultation-initial',sid,'second-request')
    clock[0]+=4000;checkout.sweep()
    with s.store.read() as c:
        assert one(c,slots,slots.c.id==sid)['status']=='held'
        assert any(row['kind']=='checkout_creation_uncertain' for row in rows(c,issues))


def test_late_paid_expired_hold_does_not_displace_another_buyer(flow):
    s,_,_,gateway,checkout,_=flow;first=reserve(flow)
    gateway.sessions[first['id']]['status']='expired';checkout.expire(gateway.sessions[first['id']])
    second=reserve(flow,owner='another-owner-token-000000000',email='second@example.invalid')
    paid(s,second);paid(s,first,event='evt_late')
    with s.store.read() as c:
        assert len(rows(c,bookings))==1 and len(rows(c,grants))==2
        assert any(row['kind']=='paid_consultation_needs_review' for row in rows(c,issues))


def test_mismatched_email_is_flagged_without_booking(flow):
    s,*_=flow;hold=reserve(flow);paid(s,hold,email='different@example.invalid')
    with s.store.read() as c:
        assert not rows(c,bookings)
        assert one(c,holds,holds.c.id==hold['id'])['status']=='review'


def test_blocked_or_unapproved_schedule_cannot_be_bought(flow):
    s,_,_,_,checkout,_=flow
    sid=s.publish_slot(int(candidate_slots()[0][0].timestamp())+86400*70)
    with pytest.raises(RuleError): checkout.checkout('owner','test@example.invalid','consultation-initial',sid,'request-id-0001')


def submission(booking_id,request='submit-request-0001',**answers):
    return IntakeSubmission(booking_id=booking_id,request_id=request,consent=True,
        answers={'preferred_name':'Test learner','goals':'Improve my routine','medical_history':'SYNTHETIC-MEDICAL-DETAIL',**answers})


def test_private_intake_encrypted_append_only_and_coach_access(flow):
    s,settings,*_=flow;hold=reserve(flow);paid(s,hold);token=activate(s)
    bid=s.me(token)['appointments'][0]['id'];intake=IntakeService(s)
    body=submission(bid);intake.submit(token,body);intake.submit(token,body)
    intake.submit(token,submission(bid,request='updated-request-0002',goals='Updated goal'))
    assert intake.get(token,bid)['answers']['goals']=='Updated goal'
    with s.store.read() as c:
        assert len(rows(c,intakes))==2
        assert all('SYNTHETIC' not in row['payload'] for row in rows(c,intakes))
        messages=[json.loads(s.cipher.decrypt(row['payload'].encode())) for row in rows(c,outbox)]
        assert all('SYNTHETIC-MEDICAL' not in message['body'] for message in messages)
    other=member(s,email='other@example.invalid',source='cs:other')
    with pytest.raises(RuleError): intake.get(other,bid)
    with pytest.raises(RuleError): intake.submit(other,submission(bid))
    with pytest.raises(RuleError): intake.coach_get(other,bid)
    s.request_activation(settings.coach_email);coach=activate(s,settings.coach_email)
    versions=intake.coach_get(coach,bid)['versions']
    assert [v['version'] for v in versions]==[2,1]
    assert versions[0]['answers']['goals']=='Updated goal'
    assert 'SYNTHETIC' not in json.dumps(s.admin_summary())


def test_intake_requires_consent_and_rejects_changed_duplicate(flow):
    s,*_=flow;hold=reserve(flow);paid(s,hold);token=activate(s)
    bid=s.me(token)['appointments'][0]['id'];intake=IntakeService(s)
    body=submission(bid);body.consent=False
    with pytest.raises(RuleError): intake.submit(token,body)
    body.consent=True;intake.submit(token,body)
    with pytest.raises(RuleError): intake.submit(token,submission(bid,goals='Changed'))


def test_gates_and_http_owner_boundary(flow):
    s,settings,clock,gateway,checkout,sid=flow
    app=create_app(settings,s.store,gateway=gateway,clock=lambda:clock[0])
    with TestClient(app) as client:
        assert client.get('/consultation').status_code==200
        assert client.get('/intake').status_code==200
        assert client.get('/api/consultation').json()['enabled']
        assert client.cookies.get('mb_checkout_browser')
        body=dict(email='student@example.invalid',plan='consultation-initial',slot_id=sid,request_id='http-request-0001')
        assert client.post('/api/consultation/checkout',json=body).status_code==403
        response=client.post('/api/consultation/checkout',json=body,headers={'Origin':settings.public_url})
        assert response.status_code==200
        assert client.get('/api/consultation/status').json()['status']=='pending'
        assert client.get('/api/intake/unknown').status_code==401
        invalid=client.post('/api/intake',json={'secret_health_detail':'DO-NOT-ECHO'},headers={'Origin':settings.public_url})
        assert invalid.status_code==422 and 'DO-NOT-ECHO' not in invalid.text
    settings.consultation_checkout_enabled=False
    assert checkout.available()=={'enabled':False,'slots':[]}
    with pytest.raises(RuleError): reserve(flow)


def test_intake_configuration_requires_reviewed_notice(flow):
    settings=flow[1];settings.intake_privacy_url=''
    with pytest.raises(ValueError): settings.validate()


def test_stripe_checkout_creation_is_one_time_and_idempotent(flow):
    s,settings,*_=flow;settings.price_plans={'price_test_initial':'consultation-initial'}
    gateway=object.__new__(StripeGateway);gateway.settings=settings
    context=dict(id='hold-test',email='test@example.invalid',plan='consultation-initial',expires_at=s.now()+3600,checkout_id=None)
    captured={}
    def create(params,options):
        captured.update(params=params,options=options)
        return dict(id='cs_test',url='https://checkout.stripe.com/c/pay/test',livemode=False,status='open',mode='payment',metadata={'mb_hold_id':'hold-test'},expires_at=context['expires_at'])
    gateway.client=SimpleNamespace(v1=SimpleNamespace(
        prices=SimpleNamespace(retrieve=lambda _:dict(livemode=False,currency='myr',unit_amount=19900,recurring=None)),
        checkout=SimpleNamespace(sessions=SimpleNamespace(create=create))))
    gateway.consultation_checkout(context)
    assert captured['params']['mode']=='payment'
    assert captured['params']['metadata']=={'mb_hold_id':'hold-test'}
    assert captured['params']['allowed_payment_method_types']==['card']
    assert 'payment_method_types' not in captured['params']
    assert captured['options']['idempotency_key']=='mb-consultation-hold-test'
    assert captured['params']['success_url'].endswith('/consultation?payment=returned')


def test_resume_after_cancel_or_unknown_creation_reuses_same_checkout(flow):
    s,_,_,gateway,checkout,_=flow;hold=reserve(flow)
    result=checkout.resume('browser-owner-token-000000000000')
    assert result['hold_id']==hold['id'] and len(gateway.sessions)==1
    with pytest.raises(RuleError): checkout.resume('different-browser-owner')


def test_approved_schedule_publication_does_not_reopen_closed_dates(flow):
    s,_,_,_,_,sid=flow;s.close_slot(sid)
    result=s.publish_approved_slots();assert result['created']==141
    assert s.publish_approved_slots()['created']==0
    with s.store.read() as c: assert one(c,slots,slots.c.id==sid)['status']=='closed'


def test_signed_webhook_confirms_booking_not_browser_return(flow):
    s,settings,clock,gateway,checkout,sid=flow
    app=create_app(settings,s.store,gateway=gateway,clock=lambda:clock[0])
    with TestClient(app) as client:
        client.get('/api/consultation')
        body=dict(email='student@example.invalid',plan='consultation-initial',slot_id=sid,request_id='signed-request-0001')
        result=client.post('/api/consultation/checkout',json=body,headers={'Origin':settings.public_url}).json()
        with s.store.read() as c: hold=dict(one(c,holds,holds.c.id==result['hold_id']))
        assert client.get('/consultation?payment=returned').status_code==200
        assert client.get('/api/consultation/status').json()['status']=='pending'
        gateway.checkout=lambda checkout_id,at:dict(source_id='cs:'+checkout_id,plan=hold['plan'],
            email=hold['email'],hold_id=hold['id'],paid_at=at)
        timestamp=int(system_time.time())
        event={'id':'evt_signed_booking','created':clock[0],'livemode':False,'type':'checkout.session.completed',
               'data':{'object':{'id':hold['checkout_id']}}}
        raw=json.dumps(event).encode()
        signed=hmac.new(settings.webhook_secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        headers={'stripe-signature':f't={timestamp},v1={signed}'}
        assert client.post('/stripe/webhook',content=raw+b' ',headers=headers).status_code==400
        assert client.get('/api/consultation/status').json()['status']=='pending'
        assert client.post('/stripe/webhook',content=raw,headers=headers).status_code==200
        assert client.get('/api/consultation/status').json()['status']=='booked'
        assert client.post('/stripe/webhook',content=raw,headers=headers).status_code==200
        with s.store.read() as c: assert len(rows(c,bookings))==1


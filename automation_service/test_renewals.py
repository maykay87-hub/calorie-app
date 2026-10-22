"""Returning-student continuation tests; no real Stripe calls or charges."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from .app import create_app
from .renewals import RenewalService
from .service import RuleError
from .store import accounts, grants, renewals, subscriptions, rows, one
from .stripe_gateway import StripeGateway
from .test_service import setup, member, purchase, activate, NOW, PASSWORD


def expired_member(setup):
    s, settings, clock=setup
    settings.renewal_enabled=True
    token=member(s)
    clock[0]+=8*86400
    token=s.login('student@example.invalid',PASSWORD)
    return s, settings, clock, token


def checkout_result(context):
    return {'id':'cs_'+context['request_key'],
            'url':'https://checkout.stripe.com/c/pay/'+context['request_key'],
            'customer_id':'cus_synthetic', 'expires_at':context['expires_at']}


def test_continuation_requires_history_and_preserves_unexpired_rights(setup):
    s, settings, clock=setup
    token=member(s)
    flow=RenewalService(s,SimpleNamespace(renewal_checkout=lambda _:pytest.fail('Ineligible checkout called Stripe')))
    assert flow.status(token)=={'eligible':False,'reason':'not_open'}
    settings.renewal_enabled=True
    assert flow.status(token)['reason']=='existing_access'
    with pytest.raises(RuleError): flow.checkout(token,True)
    clock[0]+=8*86400
    token=s.login('student@example.invalid',PASSWORD)
    assert flow.status(token)['eligible']
    with s.store.write() as c:
        c.execute(grants.update().values(revoked=True))
    assert flow.status(token)['reason']=='no_paid_history'


def test_future_or_unstarted_rights_cannot_be_replaced_by_renewal(setup):
    s, settings, clock, token=expired_member(setup)
    with s.store.write() as c:
        c.execute(grants.update().values(starts_at=None,ends_at=None))
    flow=RenewalService(s,None)
    assert not flow.status(token)['eligible']
    with s.store.write() as c:
        c.execute(grants.update().values(starts_at=clock[0]+86400,ends_at=clock[0]+180*86400))
    assert flow.status(token)['reason']=='existing_access'


def test_subscription_cancellation_cap_is_respected(setup):
    s, settings, clock, token=expired_member(setup)
    with s.store.write() as c:
        c.execute(grants.update().values(subscription_id='sub_capped',ends_at=clock[0]+86400))
        c.execute(subscriptions.insert().values(id='sub_capped',cap_at=clock[0]-1,event_time=clock[0]))
    assert RenewalService(s,None).status(token)['eligible']


def test_checkout_retries_share_one_reservation_and_do_not_grant_access(setup):
    s, settings, clock, token=expired_member(setup)
    contexts=[]
    gateway=SimpleNamespace(renewal_checkout=lambda ctx:contexts.append(ctx) or checkout_result(ctx))
    flow=RenewalService(s,gateway)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:flow.checkout(token,True),range(2)))
    assert results[0]==results[1]
    assert len({c['request_key'] for c in contexts})==1
    with s.store.read() as c:
        assert len(rows(c,renewals))==1
        assert len(rows(c,grants))==1
    assert not s.me(token)['active']
    s.fulfill('evt_renewal','invoice.paid',dict(purchase(plan='tracker-monthly',source='in:renewal',customer='cus_synthetic'),
        subscription_id='sub_paid',starts_at=clock[0],ends_at=clock[0]+30*86400))
    assert s.me(token)['active'] and s.me(token)['credits']==0
    assert flow.status(token)['reason']=='existing_access'


def test_network_failure_retains_idempotency_and_url_validation_blocks_foreign_destinations(setup):
    s, settings, clock, token=expired_member(setup)
    captured=[]
    def fail(ctx):
        captured.append(ctx)
        raise ConnectionError('private-provider-diagnostic')
    gateway=SimpleNamespace(renewal_checkout=fail)
    flow=RenewalService(s,gateway)
    with pytest.raises(ConnectionError): flow.checkout(token,True)
    gateway.renewal_checkout=lambda ctx:captured.append(ctx) or dict(checkout_result(ctx),url='https://evil.invalid/pay')
    with pytest.raises(ValueError): flow.checkout(token,True)
    assert captured[0]['request_key']==captured[1]['request_key']
    with s.store.read() as c: assert rows(c,renewals)[0]['checkout_url'] is None


def test_expired_reservation_gets_new_key_but_consent_is_required(setup):
    s, settings, clock, token=expired_member(setup)
    keys=[]
    flow=RenewalService(s,SimpleNamespace(renewal_checkout=lambda ctx:keys.append(ctx['request_key']) or checkout_result(ctx)))
    with pytest.raises(RuleError): flow.checkout(token,False)
    flow.checkout(token,True)
    clock[0]+=3601
    flow.checkout(token,True)
    assert len(set(keys))==2


def test_http_renewal_requires_signin_same_origin_and_strict_consent(setup):
    s, settings, clock, token=expired_member(setup)
    contexts=[]
    app=create_app(settings,s.store,gateway=SimpleNamespace(renewal_checkout=lambda ctx:contexts.append(ctx) or checkout_result(ctx)),
                   sender=lambda *_:None,clock=lambda:clock[0])
    with TestClient(app,base_url=settings.public_url) as client:
        assert client.get('/api/renewal').status_code==401
        client.cookies.set('mb_session',token)
        assert client.get('/api/renewal').json()['eligible']
        assert client.post('/api/renewal',json={'agreed':True}).status_code==403
        headers={'origin':settings.public_url}
        assert client.post('/api/renewal',json={'agreed':'true'},headers=headers).status_code==422
        assert client.post('/api/renewal',json={'agreed':False},headers=headers).status_code==400
        assert client.post('/api/renewal',json={'agreed':True},headers=headers).status_code==200
        client.get('/?renewal=complete')
        assert not client.get('/api/me').json()['active']


def synthetic_gateway(settings, statuses=(), existing=True, session_status='open'):
    calls=[]
    def customer(cid='cus_synthetic'):
        return {'id':cid,'email':'student@example.invalid','livemode':False}
    def create_session(params,options):
        calls.append((params,options))
        return {'id':'cs_synthetic','livemode':False,'status':session_status,'customer':'cus_synthetic',
                'url':'https://checkout.stripe.com/c/pay/cs_synthetic','expires_at':params['expires_at']}
    gateway=StripeGateway.__new__(StripeGateway);gateway.settings=settings
    gateway.client=SimpleNamespace(v1=SimpleNamespace(
        prices=SimpleNamespace(retrieve=lambda _:dict(livemode=False,currency='myr',unit_amount=4800,recurring={'interval':'month','interval_count':1})),
        customers=SimpleNamespace(list=lambda _:dict(has_more=False,data=[customer()] if existing else []),
                                  retrieve=customer,create=lambda params,options:customer()),
        subscriptions=SimpleNamespace(list=lambda _:dict(has_more=False,data=[{'status':v} for v in statuses])),
        checkout=SimpleNamespace(sessions=SimpleNamespace(create=create_session,
            retrieve=lambda _:dict(livemode=False,status='complete',customer='cus_synthetic')))))
    return gateway,calls


def context():
    return dict(email='student@example.invalid',account_id='synthetic-account',customer_ids=[],
                request_key='synthetic-request',expires_at=NOW+3600,checkout_id=None)


@pytest.mark.parametrize('status',['active','trialing','past_due','unpaid','incomplete','paused'])
def test_stripe_existing_subscription_or_pending_payment_blocks_second_purchase(setup,status):
    _,settings,_=setup
    gateway,calls=synthetic_gateway(settings,statuses=[status])
    with pytest.raises(RuleError,match='已有订阅'): gateway.renewal_checkout(context())
    assert not calls


def test_gateway_pins_customer_price_quantity_and_expiry_without_trial_conversion(setup):
    _,settings,_=setup
    gateway,calls=synthetic_gateway(settings,statuses=['canceled','incomplete_expired'],existing=False)
    result=gateway.renewal_checkout(context())
    params,options=calls[0]
    assert params['mode']=='subscription' and params['customer']=='cus_synthetic'
    assert params['line_items']==[{'price':'price_test_monthly','quantity':1}]
    assert params['expires_at']==context()['expires_at'] and 'subscription_data' not in params
    assert options['idempotency_key']=='mb-renewal-synthetic-request'
    assert result['customer_id']=='cus_synthetic'


def test_completed_checkout_cannot_be_reopened_as_a_new_purchase(setup):
    _,settings,_=setup
    gateway,calls=synthetic_gateway(settings)
    ctx=dict(context(),checkout_id='cs_already_complete')
    with pytest.raises(RuleError,match='付款正在处理'): gateway.renewal_checkout(ctx)
    assert not calls


def test_adding_continuation_table_preserves_existing_paid_records(setup):
    s,settings,clock,token=expired_member(setup)
    before=s.me(token)
    # Disposable synthetic database simulates the pre-continuation schema.
    renewals.drop(s.store.engine)
    from .store import Store
    reopened=Store(settings.database_url)
    with reopened.read() as c:
        assert len(rows(c,grants))==1 and not rows(c,renewals)
        assert rows(c,accounts)[0]['username']==before['username']


def test_cached_session_keeps_original_customer_when_another_identity_exists(setup):
    _,settings,_=setup
    gateway,calls=synthetic_gateway(settings)
    gateway.client.v1.checkout.sessions.retrieve=lambda _:dict(id='cs_cached',livemode=False,status='open',
        customer='cus_synthetic',url='https://checkout.stripe.com/c/pay/cs_cached',expires_at=context()['expires_at'])
    ctx=dict(context(),customer_ids=['cus_aaa'],customer_id='cus_synthetic',checkout_id='cs_cached')
    assert gateway.renewal_checkout(ctx)['customer_id']=='cus_synthetic'
    assert not calls

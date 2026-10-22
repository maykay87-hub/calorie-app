"""Synthetic event wakeups. No Google API, SMTP or live student data."""
from types import SimpleNamespace
import json
from fastapi.testclient import TestClient
import pytest
from .app import create_app
from .jobs import JobDispatcher
from .store import outbox, grants, rows
from .test_service import setup, purchase, activate, member, signed, NOW


def test_task_only_contains_worker_auth_and_hashed_identity(setup):
    _, settings, _ = setup
    settings.task_queue = 'projects/synthetic/locations/asia-southeast1/queues/email'
    settings.public_url = 'https://members.example.invalid'
    calls = []
    client = SimpleNamespace(post=lambda url, **kw: calls.append((url, kw)) or SimpleNamespace(status_code=200))
    dispatcher = JobDispatcher(settings, client)
    assert dispatcher.enqueue('activation:synthetic-sensitive-identity')
    url, kw = calls[0]
    task = kw['json']['task']
    assert url.endswith('/queues/email/tasks') and kw['timeout'] == 5
    assert task['httpRequest']['url'] == settings.public_url + '/admin/run-jobs'
    assert task['httpRequest']['headers']['Authorization'] == 'Bearer ' + settings.admin_key
    assert task['httpRequest']['body'] == 'e30='
    assert 'synthetic-sensitive-identity' not in json.dumps(task)
    assert not dispatcher.settings.live


def test_queue_disabled_duplicate_and_provider_failure(setup):
    _, settings, _ = setup
    client = SimpleNamespace(post=lambda *_a, **_k: pytest.fail('Disabled queue called a provider'))
    dispatcher = JobDispatcher(settings, client)
    assert dispatcher.enqueue('event') is False
    settings.task_queue = 'projects/test/locations/asia-southeast1/queues/mail'
    dispatcher.client = SimpleNamespace(post=lambda *_a, **_k: SimpleNamespace(status_code=409))
    assert dispatcher.enqueue('event') is False
    dispatcher.client = SimpleNamespace(post=lambda *_a, **_k: SimpleNamespace(status_code=503))
    with pytest.raises(RuntimeError, match='Job dispatch unavailable'):
        dispatcher.enqueue('event')


def test_paid_webhook_wakes_worker_without_sending_in_webhook_and_replay_keeps_one_grant(setup):
    s, settings, clock = setup
    wakes = []
    gateway = SimpleNamespace(checkout=lambda *_: purchase())
    app = create_app(settings, s.store, gateway=gateway,
        sender=lambda *_: pytest.fail('SMTP must run only in worker request'), clock=lambda: clock[0],
        job_dispatcher=SimpleNamespace(enqueue=lambda key: wakes.append(key)))
    event = {'id':'evt_queue','created':NOW,'livemode':False,'type':'checkout.session.completed','data':{'object':{'id':'cs_synthetic'}}}
    raw, headers = signed(event, settings)
    with TestClient(app, base_url=settings.public_url) as client:
        assert client.post('/stripe/webhook',content=raw,headers=headers).status_code == 200
        assert client.post('/stripe/webhook',content=raw,headers=headers).json()['result'] == 'duplicate'
        assert client.post('/stripe/webhook',content=raw+b'x',headers=headers).status_code == 400
        assert wakes == ['stripe:evt_queue', 'stripe:evt_queue']
        with s.store.read() as c:
            assert len(rows(c, grants)) == 1
            assert all(m['status'] == 'pending' for m in rows(c, outbox))


def test_queue_failure_keeps_payment_and_worker_can_recover_mail(setup):
    s, settings, clock = setup
    def fail(_): raise ConnectionError('private-provider-diagnostic')
    sent = []
    app = create_app(settings, s.store, gateway=SimpleNamespace(checkout=lambda *_: purchase()),
        sender=lambda key, payload: sent.append(payload), clock=lambda: clock[0],
        job_dispatcher=SimpleNamespace(enqueue=fail))
    event = {'id':'evt_queue_fail','created':NOW,'livemode':False,'type':'checkout.session.completed','data':{'object':{'id':'cs_synthetic'}}}
    raw, headers = signed(event, settings)
    with TestClient(app, base_url=settings.public_url) as client:
        result = client.post('/stripe/webhook', content=raw, headers=headers)
        assert result.status_code == 200 and 'private-provider' not in result.text
        assert any(i['kind'] == 'job_dispatch_failed' for i in s.admin_summary()['issues'])
        assert client.post('/admin/run-jobs').status_code == 401
        response = client.post('/admin/run-jobs', headers={'authorization':'Bearer '+settings.admin_key})
        assert response.status_code == 200 and response.json()['sent'] == 2
        assert len(sent) == 2
        assert s.me(activate(s))['credits'] == 1


def test_activation_only_wakes_for_queued_email_and_booking_is_durable(setup):
    s, settings, clock = setup
    token = member(s)
    wakes = []
    app = create_app(settings, s.store, sender=lambda *_: None, clock=lambda: clock[0],
        job_dispatcher=SimpleNamespace(enqueue=lambda key: wakes.append(key)))
    with TestClient(app, base_url=settings.public_url) as client:
        headers = {'origin':settings.public_url}
        missing = client.post('/api/request-activation',json={'email':'missing@example.invalid'},headers=headers)
        assert missing.status_code == 200 and not wakes
        known = client.post('/api/request-activation',json={'email':'student@example.invalid'},headers=headers)
        assert known.json() == missing.json() and len(wakes) == 1
        assert wakes[0].startswith('activation:') and '@' not in wakes[0]
        client.cookies.set('mb_session', token)
        sid = s.publish_slot(NOW+2*86400)
        body = {'slot_id':sid,'request_id':'booking-dispatch-synthetic'}
        booking = client.post('/api/book',json=body,headers=headers)
        assert booking.status_code == 200
        assert wakes[-1] == 'booking:' + booking.json()['booking_id']
        again = client.post('/api/book',json=body,headers=headers)
        assert again.json() == booking.json() and len(s.me(token)['appointments']) == 1


def test_queue_configuration_rejected_before_connection(setup):
    _, settings, _ = setup
    settings.task_queue = 'https://arbitrary.example.invalid'
    with pytest.raises(ValueError, match='Cloud Tasks queue'):
        settings.validate()

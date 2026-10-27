"""Complete HTTP buyer journey with synthetic Stripe reads and captured emails.

These tests exercise the real service, DB transactions, intake and Tracker bridge.
Provider delivery, hosted PostgreSQL and browser rendering are separate checks.
"""
import hashlib
import hmac
import io
import json
import time

from fastapi.testclient import TestClient

import member_access
from .app import create_app
from .availability import candidate_slots
from .store import Store, accounts, bookings, grants, intakes, outbox, one, rows
from .test_consultation_checkout import FakeGateway
from .test_service import setup, PASSWORD


def post_event(client, settings, clock, event_id, session_id):
    raw = json.dumps({'id': event_id, 'created': clock[0], 'livemode': False,
                      'type': 'checkout.session.completed',
                      'data': {'object': {'id': session_id, 'email': 'untrusted@example.invalid'}}}).encode()
    at = int(time.time())
    signed = hmac.new(settings.webhook_secret.encode(), str(at).encode() + b'.' + raw,
                      hashlib.sha256).hexdigest()
    return client.post('/stripe/webhook', content=raw,
                       headers={'stripe-signature': f't={at},v1={signed}'})


def test_initial_consultation_payment_activation_preparation_tracker_and_restart(setup):
    service, settings, clock = setup
    settings.consultation_checkout_enabled = settings.intake_enabled = True
    settings.legacy_link_enabled = False
    settings.intake_privacy_url = 'https://example.invalid/privacy'
    settings.intake_consent_version = 'synthetic-test-v1'
    settings.coach_email = 'coach@example.invalid'
    settings.validate()
    first_start = int(candidate_slots()[0][0].timestamp())
    slot_id = service.publish_slot(first_start)
    gateway = FakeGateway()
    paid_sessions = {}
    gateway.checkout = lambda sid, at: dict(paid_sessions[sid], paid_at=at)
    mail = []
    app = create_app(settings, service.store, gateway=gateway,
                     sender=lambda key, payload: mail.append((key, payload)), clock=lambda: clock[0])
    origin = {'Origin': settings.public_url}
    admin = {'Authorization': 'Bearer ' + settings.admin_key}
    email = 'journey@example.invalid'
    with TestClient(app) as buyer, TestClient(app) as stranger:
        assert buyer.get('/consultation?plan=consultation-initial').status_code == 200
        assert buyer.get('/api/consultation').json()['slots'][0]['id'] == slot_id
        body = {'email': email, 'plan': 'consultation-initial', 'slot_id': slot_id,
                'request_id': 'buyer-journey-request-0001'}
        checkout = buyer.post('/api/consultation/checkout', json=body, headers=origin)
        assert checkout.status_code == 200
        hold_id = checkout.json()['hold_id']
        sid = gateway.sessions[hold_id]['id']
        assert buyer.get('/consultation?payment=returned').status_code == 200
        assert buyer.get('/api/consultation/status').json()['status'] == 'pending'
        with service.store.read() as c:
            assert not rows(c, grants) and not rows(c, bookings)
        # Canonical paid state, rather than browser redirect or webhook email, controls grants.
        paid_sessions[sid] = {'source_id': 'cs:' + sid, 'email': email,
                              'plan': 'consultation-initial', 'hold_id': hold_id,
                              'customer_id': 'cus_synthetic_journey', 'payment_intent': 'pi_synthetic_journey'}
        assert post_event(buyer, settings, clock, 'evt_journey_paid', sid).status_code == 200
        assert post_event(buyer, settings, clock, 'evt_journey_paid', sid).json()['result'] == 'duplicate'
        assert post_event(buyer, settings, clock, 'evt_journey_second_notification', sid).status_code == 200
        assert buyer.get('/api/consultation/status').json()['status'] == 'booked'
        assert stranger.get('/api/consultation/status').json()['status'] == 'none'
        assert buyer.get('/api/me').status_code == 401
        assert not mail  # SMTP is never performed inside payment reconciliation.
        assert buyer.post('/admin/run-jobs', json={}, headers=admin).status_code == 200
        activation = next(payload for _, payload in mail if payload['kind'] == 'activation')
        assert activation['to'] == email
        token = activation['body'].split('#activate=')[1].split()[0]
        activate = buyer.post('/api/activate', json={'token': token, 'password': PASSWORD}, headers=origin)
        assert activate.status_code == 200
        assert buyer.post('/api/activate', json={'token': token, 'password': PASSWORD}, headers=origin).status_code == 400
        me = buyer.get('/api/me').json()
        assert me['active'] and me['ends_at'] == clock[0] + 7 * 86400
        assert me['credits'] == 0 and me['plans'] == ['consultation-initial']
        assert len(me['appointments']) == 1
        booking_id = me['appointments'][0]['id']
        answers = {'preferred_name': 'SYNTHETIC participant', 'goals': 'SYNTHETIC meal planning',
                   'medical_history': 'SYNTHETIC PRIVATE HEALTH ANSWER'}
        preparation = {'booking_id': booking_id, 'request_id': 'journey-preparation-0001',
                       'consent': True, 'answers': answers}
        assert buyer.post('/api/intake', json=preparation, headers=origin).status_code == 200
        assert buyer.post('/api/intake', json=preparation, headers=origin).status_code == 200
        assert buyer.get('/api/intake/' + booking_id).json()['answers']['goals'] == answers['goals']
        assert stranger.get('/api/intake/' + booking_id).status_code == 401
        assert buyer.get('/api/coach/intake/' + booking_id).status_code == 403
        with service.store.read() as c:
            assert len(rows(c, accounts)) == len(rows(c, grants)) == len(rows(c, bookings)) == 1
            assert len(rows(c, intakes)) == 1
            assert all('SYNTHETIC PRIVATE HEALTH ANSWER' not in row['payload'] for row in rows(c, intakes))
        # Exercise the existing Tracker client against the real protected HTTP routes.
        options = {'url': settings.public_url, 'bridge_key': settings.bridge_key}
        def opener(request, timeout):
            path = request.full_url.removeprefix(settings.public_url)
            response = buyer.request(request.get_method(), path, content=request.data, headers=dict(request.header_items()))
            assert response.status_code == 200
            return io.BytesIO(response.content)
        managed = member_access.login(options, email, PASSWORD, opener=opener)
        assert managed['username'] == me['username'] and managed['active']
        assert member_access.verify(options, managed['token'], me['username'], opener=opener)['active']
        assert buyer.post('/admin/run-jobs', json={}, headers=admin).status_code == 200
        assert all(answers['medical_history'] not in payload['body'] for _, payload in mail)
        assert sum(payload['kind'] == 'booking' for _, payload in mail) == 1
        # The verified coach can inspect the version; the buyer cannot inspect other accounts.
        assert buyer.post('/api/request-activation', json={'email': settings.coach_email}, headers=origin).status_code == 200
        buyer.post('/admin/run-jobs', json={}, headers=admin)
        coach_message = next(payload for _, payload in mail if payload['kind'] == 'activation' and payload['to'] == settings.coach_email)
        coach_token = coach_message['body'].split('#activate=')[1].split()[0]
        with TestClient(app) as coach:
            assert coach.post('/api/activate', json={'token': coach_token, 'password': PASSWORD}, headers=origin).status_code == 200
            versions = coach.get('/api/coach/intake/' + booking_id).json()['versions']
            assert versions[0]['answers']['medical_history'] == answers['medical_history']
    # Restart the application with the same store/encryption key; all buyer data survives.
    restarted = create_app(settings, Store(settings.database_url), gateway=gateway,
                           sender=lambda key, payload: mail.append((key, payload)), clock=lambda: clock[0])
    with TestClient(restarted) as buyer:
        assert buyer.post('/api/login', json={'email': email, 'password': PASSWORD}, headers=origin).status_code == 200
        assert buyer.get('/api/me').json()['username'] == me['username']
        assert buyer.get('/api/intake/' + booking_id).json()['submitted']
        clock[0] += 7 * 86400
        buyer.post('/api/login', json={'email': email, 'password': PASSWORD}, headers=origin)
        assert buyer.get('/api/me').json()['active'] is False
        assert buyer.get('/api/me').json()['appointments'][0]['id'] == booking_id


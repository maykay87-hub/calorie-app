"""Receiver contract tests; synthetic signatures, mocked DB, no network or secrets."""
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi.testclient import TestClient
from automation_staging import webhook_app

SECRET = 'whsec_synthetic_unit_test_only'

@pytest.fixture
def receiver(monkeypatch):
    monkeypatch.setenv('MAY_BLOOM_DEPLOYMENT', 'staging')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', SECRET)
    monkeypatch.setenv('STAGING_DATABASE_URL', 'synthetic-db-not-a-connection')
    connect = MagicMock()
    monkeypatch.setattr(webhook_app.psycopg, 'connect', connect)
    return TestClient(webhook_app.app), connect

def event_body(**overrides):
    event = dict(id='evt_synthetic_contract', object='event', type='checkout.session.completed',
                 livemode=False, data={'object': {'id': 'cs_test_synthetic'}})
    event.update(overrides)
    return json.dumps(event).encode()

def signature(body, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(SECRET.encode(), str(timestamp).encode() + b'.' + body, hashlib.sha256).hexdigest()
    return f't={timestamp},v1={digest}'

def send(client, body, signed=None):
    return client.post('/stripe/webhook', content=body,
                       headers={'Stripe-Signature': signed or signature(body)})

def test_health_keeps_fulfillment_disabled(receiver):
    client, connect = receiver
    assert client.get('/health').json() == {'status': 'ok', 'mode': 'staging', 'fulfillment': 'disabled'}
    connect.assert_not_called()

def test_non_staging_fails_closed(receiver, monkeypatch):
    client, connect = receiver
    monkeypatch.setenv('MAY_BLOOM_DEPLOYMENT', 'production')
    assert send(client, event_body()).status_code == 503
    connect.assert_not_called()

@pytest.mark.parametrize('missing', ['STRIPE_WEBHOOK_SECRET', 'STAGING_DATABASE_URL'])
def test_missing_configuration_does_not_write(receiver, monkeypatch, missing):
    client, connect = receiver
    monkeypatch.delenv(missing)
    assert send(client, event_body()).status_code == 503
    connect.assert_not_called()

def test_missing_signature_does_not_write(receiver):
    client, connect = receiver
    assert client.post('/stripe/webhook', content=event_body()).status_code == 503
    connect.assert_not_called()

def test_invalid_signature_does_not_write(receiver):
    client, connect = receiver
    assert send(client, event_body(), 't=1,v1=invalid').status_code == 400
    connect.assert_not_called()

def test_tampered_body_does_not_write(receiver):
    client, connect = receiver
    assert send(client, event_body(id='evt_tampered'), signature(event_body())).status_code == 400
    connect.assert_not_called()

def test_expired_signature_does_not_write(receiver):
    client, connect = receiver
    body = event_body()
    assert send(client, body, signature(body, int(time.time()) - 600)).status_code == 400
    connect.assert_not_called()

def test_malformed_json_does_not_write(receiver):
    client, connect = receiver
    assert send(client, b'{invalid-json').status_code == 400
    connect.assert_not_called()

def test_invalid_event_id_does_not_write(receiver):
    client, connect = receiver
    assert send(client, event_body(id=123)).status_code == 400
    connect.assert_not_called()

def test_valid_signature_acknowledges_after_db_transaction(receiver):
    client, connect = receiver
    response = send(client, event_body())
    assert response.status_code == 200
    assert response.json() == {'received': True}
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == ('evt_synthetic_contract', 'checkout.session.completed')
    connect.return_value.__exit__.assert_called_once_with(None, None, None)

def test_database_failure_is_retryable_without_leaking_details(receiver):
    client, connect = receiver
    connect.side_effect = psycopg.OperationalError('sensitive connection failure detail')
    response = send(client, event_body())
    assert response.status_code == 503
    assert response.json() == {'detail': 'Event persistence unavailable'}

def test_insert_failure_is_retryable(receiver):
    client, connect = receiver
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = psycopg.OperationalError('synthetic insert failure')
    assert send(client, event_body()).status_code == 503

def test_commit_failure_is_retryable(receiver):
    client, connect = receiver
    connect.return_value.__exit__.side_effect = psycopg.OperationalError('synthetic commit failure')
    assert send(client, event_body()).status_code == 503

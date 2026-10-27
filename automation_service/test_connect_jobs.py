"""Sandbox provisioning contracts; no Google API, credentials or email traffic."""
import copy
import urllib.error
import pytest
from fastapi.testclient import TestClient
from .app import create_app
from .scripts import connect_jobs as jobs
from .test_service import setup


def service():
    return {'metadata': {'labels': {'cloud.googleapis.com/location': 'asia-southeast1'}},
            'spec': {'template': {'spec': {'containers': [{'env': [
                {'name': 'MB_STRIPE_LIVE', 'value': 'false'},
                {'name': 'MB_PUBLIC_URL', 'value': 'https://synthetic.asia-southeast1.run.app'},
                {'name': 'MB_ADMIN_KEY', 'valueFrom': {'secretKeyRef': {'name': 'synthetic-key', 'key': '1'}}}]}]}}}}


def test_preflight_rejects_live_and_untrusted_origins_before_changes():
    source = service()
    assert jobs.validate_service(source, 'asia-southeast1')[1]['key'] == '1'
    for value in ['true', '', 'TRUE']:
        source['spec']['template']['spec']['containers'][0]['env'][0]['value'] = value
        with pytest.raises(jobs.SetupError):
            jobs.validate_service(source, 'asia-southeast1')
    for value in ['https://example.invalid', 'https://synthetic.run.app/path',
                  'https://user:secret@synthetic.run.app', 'https://synthetic.run.app?secret=private']:
        source = service()
        source['spec']['template']['spec']['containers'][0]['env'][1]['value'] = value
        with pytest.raises(jobs.SetupError):
            jobs.validate_service(source, 'asia-southeast1')


class FakeCloud:
    def __init__(self, exists=False, overrides=False):
        self.calls = []
        self.exists, self.overrides = exists, overrides

    def request(self, method, url, body=None, missing=False):
        self.calls.append((method, url, copy.deepcopy(body)))
        if method == 'GET':
            if not self.exists:
                return None
            if '/queues/' in url:
                return {'httpTarget': {'uriOverride': {}}} if self.overrides else {'name': 'synthetic'}
            return {'httpTarget': {'uri': 'https://synthetic.run.app/admin/run-jobs'}}
        if url.endswith(':getIamPolicy'):
            return {'etag': 'synthetic-etag', 'bindings': [{'role': 'roles/viewer', 'members': ['user:synthetic@example.invalid']}]}
        return {}


@pytest.mark.parametrize('exists', [False, True])
def test_connect_create_and_update_preserve_iam_and_keep_secret_out_of_process_args(monkeypatch, exists):
    cloud = FakeCloud(exists)
    commands = []
    monkeypatch.setattr(jobs, 'gcloud', lambda *args: commands.append(args))
    monkeypatch.setattr(jobs, 'request_json', lambda *args: {'sent': 0})
    secret = 'synthetic-private-worker-key'
    assert jobs.connect(cloud, 'synthetic', 'asia-southeast1', 'member-staging',
                        'runtime@synthetic.iam.gserviceaccount.com', 'https://synthetic.run.app', secret) == 0
    assert secret not in str(commands)
    assert '--update-env-vars=MB_TASK_QUEUE=projects/synthetic/locations/asia-southeast1/queues/member-staging-mail' in commands[0]
    assert '--set-env-vars' not in str(commands)
    policy = next(body['policy'] for _, url, body in cloud.calls if url.endswith(':setIamPolicy'))
    assert policy['etag'] == 'synthetic-etag' and policy['bindings'][0]['role'] == 'roles/viewer'
    assert policy['bindings'][-1]['role'] == 'roles/cloudtasks.enqueuer'
    schedule = next(body for method, url, body in cloud.calls if method in {'POST', 'PATCH'} and '/jobs' in url)
    assert schedule['schedule'] == '*/30 * * * *'
    assert schedule['httpTarget']['headers']['Authorization'] == 'Bearer ' + secret
    assert 'oidcToken' not in schedule['httpTarget']


def test_refuse_routing_override_without_changing_queue_or_service(monkeypatch):
    cloud = FakeCloud(True, True)
    monkeypatch.setattr(jobs, 'gcloud', lambda *args: pytest.fail('Unexpected service change'))
    with pytest.raises(jobs.SetupError, match='routing overrides'):
        jobs.connect(cloud, 'synthetic', 'asia-southeast1', 'member-staging', 'runtime',
                     'https://synthetic.run.app', 'synthetic-secret')
    assert len(cloud.calls) == 1


def test_provider_error_does_not_echo_private_response(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://example.invalid', 403, 'private-secret', {}, None)
    monkeypatch.setattr(jobs.urllib.request, 'urlopen', fail)
    with pytest.raises(jobs.SetupError) as error:
        jobs.request_json('POST', 'https://example.invalid', 'private-secret', {})
    assert '403' in str(error.value) and 'private-secret' not in str(error.value)


def test_nonreserved_health_route_reports_mode_without_secrets(setup):
    s, settings, clock = setup
    with TestClient(create_app(settings, s.store, clock=lambda: clock[0])) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json() == client.get('/healthz').json() == {'ok': True, 'live': False, 'booking_enabled': True}
        assert settings.admin_key not in response.text

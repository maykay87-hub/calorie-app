"""Connect the existing sandbox member service to Cloud Tasks and Scheduler.

Run in an authenticated Cloud Shell. Defaults to a read-only preflight; --apply
creates/updates the dedicated queue and recovery job and rolls a service revision.
No secret is printed, passed as a command argument, or written to disk.
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


class SetupError(Exception):
    pass


def gcloud(*args):
    result = subprocess.run(['gcloud', *args, '--quiet'], capture_output=True, text=True)
    if result.returncode:
        raise SetupError('Google Cloud command failed; check account permissions and enabled APIs.')
    return result.stdout.strip()


class Cloud:
    def request(self, method, url, body=None, missing=False):
        token = gcloud('auth', 'print-access-token')
        return request_json(method, url, token, body, missing)


def request_json(method, url, token, body=None, missing=False):
    request = urllib.request.Request(url, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if missing and exc.code == 404:
            return None
        # Provider responses can contain authentication headers or payloads.
        raise SetupError(f'Cloud request failed (HTTP {exc.code}); no private details printed.') from None
    except (OSError, ValueError):
        raise SetupError('Cloud request failed; no private details printed.') from None


def validate_service(service, region):
    env = {item['name']: item for item in service['spec']['template']['spec']['containers'][0].get('env', [])}
    if env.get('MB_STRIPE_LIVE', {}).get('value') != 'false':
        raise SetupError('This setup is restricted to an explicitly configured Stripe sandbox service.')
    origin = env.get('MB_PUBLIC_URL', {}).get('value', '').rstrip('/')
    parsed = urlparse(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.run.app')
            or parsed.username or parsed.password or parsed.port or parsed.path or parsed.query or parsed.fragment):
        raise SetupError('Expected the existing HTTPS Cloud Run public origin.')
    if service.get('metadata', {}).get('labels', {}).get('cloud.googleapis.com/location') != region:
        raise SetupError('The service region does not match.')
    reference = env.get('MB_ADMIN_KEY', {}).get('valueFrom', {}).get('secretKeyRef', {})
    if not reference.get('name') or not reference.get('key'):
        raise SetupError('The existing admin key must reference Secret Manager.')
    return origin, reference


def connect(cloud, project, region, service, runtime, origin, admin_key):
    parent = f'projects/{project}/locations/{region}'
    queue_name = f'{parent}/queues/{service}-mail'
    queue_url = 'https://cloudtasks.googleapis.com/v2/' + queue_name
    spec = {'name': queue_name, 'rateLimits': {'maxDispatchesPerSecond': 1, 'maxConcurrentDispatches': 1},
            'retryConfig': {'maxAttempts': 5, 'minBackoff': '60s', 'maxBackoff': '3600s', 'maxDoublings': 5}}
    existing = cloud.request('GET', queue_url, missing=True)
    if existing is None:
        cloud.request('POST', 'https://cloudtasks.googleapis.com/v2/' + parent + '/queues', spec)
    else:
        # Refuse to reuse a queue with routing/auth overrides that could replace the worker credential.
        if existing.get('httpTarget') or existing.get('appEngineRoutingOverride'):
            raise SetupError('The dedicated queue has routing overrides; review it before continuing.')
        cloud.request('PATCH', queue_url + '?updateMask=rateLimits,retryConfig', spec)
    policy = cloud.request('POST', queue_url + ':getIamPolicy', {})
    member = 'serviceAccount:' + runtime
    bindings = policy.setdefault('bindings', [])
    binding = next((b for b in bindings if b['role'] == 'roles/cloudtasks.enqueuer' and not b.get('condition')), None)
    if binding is None:
        binding = {'role': 'roles/cloudtasks.enqueuer', 'members': []}
        bindings.append(binding)
    if member not in binding['members']:
        binding['members'].append(member)
        cloud.request('POST', queue_url + ':setIamPolicy', {'policy': policy})

    # Update only timeout and the queue variable; preserve all other environment and secrets.
    gcloud('run', 'services', 'update', service, '--project=' + project, '--region=' + region,
           '--timeout=600', '--update-env-vars=MB_TASK_QUEUE=' + queue_name, '--format=value(status.latestReadyRevisionName)')

    job_name = f'{parent}/jobs/{service}-recovery'
    job_url = 'https://cloudscheduler.googleapis.com/v1/' + job_name
    job = {'name': job_name, 'description': 'Member mail recovery and appointment reminders',
           'schedule': '*/30 * * * *', 'timeZone': 'Asia/Kuala_Lumpur', 'attemptDeadline': '600s',
           'retryConfig': {'retryCount': 2, 'minBackoffDuration': '60s', 'maxBackoffDuration': '600s'},
           'httpTarget': {'uri': origin + '/admin/run-jobs', 'httpMethod': 'POST',
                          'headers': {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + admin_key},
                          'body': base64.b64encode(b'{}').decode()}}
    old_job = cloud.request('GET', job_url, missing=True)
    if old_job is None:
        cloud.request('POST', 'https://cloudscheduler.googleapis.com/v1/' + parent + '/jobs', job)
    else:
        if old_job.get('httpTarget', {}).get('uri') != origin + '/admin/run-jobs':
            raise SetupError('The recovery job already targets another service; no replacement made.')
        cloud.request('PATCH', job_url + '?updateMask=description,schedule,timeZone,attemptDeadline,retryConfig,httpTarget', job)
    # A real worker response validates the private credential without exposing it.
    result = request_json('POST', origin + '/admin/run-jobs', admin_key, {})
    if not isinstance(result.get('sent'), int):
        raise SetupError('Unexpected worker response; hosted acceptance remains incomplete.')
    return result['sent']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--region', default='asia-southeast1')
    parser.add_argument('--service', default='maybloom-member-staging')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    for value in (args.project, args.region, args.service):
        if not re.fullmatch(r'[a-z][a-z0-9-]{1,62}', value):
            raise SetupError('Invalid resource identifier.')
    service = json.loads(gcloud('run', 'services', 'describe', args.service, '--project=' + args.project,
                                '--region=' + args.region, '--format=json'))
    origin, reference = validate_service(service, args.region)
    runtime = service['spec']['template']['spec'].get('serviceAccountName')
    if not runtime:
        number = gcloud('projects', 'describe', args.project, '--format=value(projectNumber)')
        runtime = number + '-compute@developer.gserviceaccount.com'
    if not args.apply:
        print('Preflight OK. Apply will connect a dedicated mail queue, queue-scoped enqueue permission,')
        print('a 600-second worker timeout and a 30-minute recovery job. No changes made.')
        return
    gcloud('services', 'enable', 'cloudtasks.googleapis.com', 'cloudscheduler.googleapis.com', '--project=' + args.project)
    secret = reference['name']
    if '/' in secret:
        raise SetupError('Use a same-project secret reference for this sandbox setup.')
    admin_key = gcloud('secrets', 'versions', 'access', reference['key'], '--secret=' + secret, '--project=' + args.project)
    if len(admin_key) < 32:
        raise SetupError('Worker credential is not valid.')
    sent = connect(Cloud(), args.project, args.region, args.service, runtime, origin, admin_key)
    print(f'Connected. Worker returned sent={sent}. Verify an event-triggered activation email and recovery execution next.')


if __name__ == '__main__':
    try:
        main()
    except (SetupError, KeyError, ValueError):
        print('Setup stopped. Check sandbox configuration, Cloud permissions and API access; no private values printed.', file=sys.stderr)
        sys.exit(1)

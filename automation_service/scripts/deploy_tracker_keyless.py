"""Owner-run, opt-in deployment of an isolated keyless Cloud Run test Tracker.

Defaults to read-only preflight. --apply creates a separate usage-billed service
with min instances zero and max one. Its login page is public; records require
the existing member login or the separate staging coach password. It never
changes the stable student app or disables service-account-key restrictions.
"""
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile

from prepare_tracker import SetupError, cloud, private_secret, service_connection


def keyless_configuration(test_sheet, production_sheet, origin, bridge, admin_password):
    if not test_sheet or not production_sheet or test_sheet == production_sheet:
        raise SetupError('Independent test and student spreadsheet identifiers are required.')
    if len(bridge) < 32 or len(admin_password) < 32 or bridge == admin_password:
        raise SetupError('Independent strong private credentials are required.')
    quote = json.dumps
    return '\n'.join([
        'staging_spreadsheet_id = ' + quote(test_sheet),
        'production_spreadsheet_id = ' + quote(production_sheet),
        '', '[passwords]', 'admin = ' + quote(admin_password),
        '', '[membership_service]', 'enabled = true', 'legacy_link_enabled = false',
        'url = ' + quote(origin), 'bridge_key = ' + quote(bridge),
        '', '[google_sheets]', 'use_runtime_identity = true', '',
    ])


def store_configuration(project, value):
    name = 'maybloom-tracker-staging-keyless-config'
    found = cloud('secrets', 'describe', name, '--project=' + project, '--format=json', missing=True)
    if found is None:
        cloud('secrets', 'create', name, '--project=' + project, '--replication-policy=automatic',
              '--data-file=-', data=value)
        version = '1'
    else:
        version = cloud('secrets', 'versions', 'add', name, '--project=' + project,
                        '--data-file=-', '--format=value(name)', data=value).rsplit('/', 1)[-1]
    if not version.isdigit():
        raise SetupError('Could not pin the private configuration version.')
    return name, version


def build_definition(image):
    return {'steps': [{'name': 'gcr.io/cloud-builders/docker',
                       'args': ['build', '--file=Dockerfile.tracker-staging', '--tag=' + image, '.']}],
            'images': [image], 'timeout': '1200s'}


def deploy_arguments(project, identity, image, secret, version):
    return ('run', 'deploy', 'maybloom-tracker-staging', '--project=' + project,
            '--region=asia-southeast1', '--image=' + image, '--service-account=' + identity,
            '--port=8080', '--memory=1Gi', '--cpu=1', '--min-instances=0', '--max-instances=1',
            '--timeout=3600', '--cpu-throttling', '--allow-unauthenticated',
            '--labels=maybloom-stage=tracker-keyless',
            '--update-env-vars=MAY_BLOOM_DEPLOYMENT=staging',
            '--update-secrets=/app/.streamlit/secrets.toml=' + secret + ':' + version,
            '--format=value(status.url)')


def checkout_source(commit, folder):
    for command in [
        ['git', 'clone', '--no-checkout', 'https://github.com/maykay87-hub/calorie-app.git', folder],
        ['git', '-C', folder, 'checkout', '--detach', commit],
    ]:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise SetupError('Could not check out the reviewed Tracker source commit.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--test-sheet', required=True)
    parser.add_argument('--production-sheet', required=True)
    parser.add_argument('--tracker-commit', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,62}', args.project):
        raise SetupError('Invalid project identifier.')
    if (any(not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', s) for s in [args.test_sheet, args.production_sheet])
            or args.test_sheet == args.production_sheet):
        raise SetupError('Supply distinct test and student spreadsheet identifiers.')
    if not re.fullmatch(r'[a-f0-9]{40}', args.tracker_commit):
        raise SetupError('Supply the complete reviewed Tracker source commit.')
    service = json.loads(cloud('run', 'services', 'describe', 'maybloom-member-staging',
                              '--project=' + args.project, '--region=asia-southeast1', '--format=json'))
    origin, reference = service_connection(service)
    old = cloud('run', 'services', 'describe', 'maybloom-tracker-staging', '--project=' + args.project,
                '--region=asia-southeast1', '--format=json', missing=True)
    if old is not None and json.loads(old).get('metadata', {}).get('labels', {}).get('maybloom-stage') != 'tracker-keyless':
        raise SetupError('The test service name is already in use; no replacement made.')
    if not args.apply:
        print('Preflight OK. No changes made. Apply creates a separate usage-billed Cloud Run test Tracker,')
        print('min instances=0, max instances=1, public login page and private member/coach records.')
        print('It uses the attached service identity, a private configuration secret and only the test Sheet.')
        print('The stable student app and key-creation security policy are not changed.')
        return
    cloud('services', 'enable', 'run.googleapis.com', 'cloudbuild.googleapis.com',
          'artifactregistry.googleapis.com', 'sheets.googleapis.com', 'drive.googleapis.com',
          '--project=' + args.project)
    identity = 'maybloom-tracker-staging@' + args.project + '.iam.gserviceaccount.com'
    found = cloud('iam', 'service-accounts', 'describe', identity, '--project=' + args.project,
                  '--format=json', missing=True)
    if found is None:
        cloud('iam', 'service-accounts', 'create', 'maybloom-tracker-staging', '--project=' + args.project,
              '--display-name=May Bloom isolated Tracker staging')
    bridge = cloud('secrets', 'versions', 'access', reference['key'], '--secret=' + reference['name'],
                   '--project=' + args.project)
    admin_password = private_secret(args.project, 'maybloom-tracker-staging-admin-password',
                                    lambda: secrets.token_urlsafe(32))
    secret, version = store_configuration(args.project,
        keyless_configuration(args.test_sheet, args.production_sheet, origin, bridge, admin_password))
    cloud('secrets', 'add-iam-policy-binding', secret, '--project=' + args.project,
          '--member=serviceAccount:' + identity, '--role=roles/secretmanager.secretAccessor')
    image = 'asia-southeast1-docker.pkg.dev/' + args.project + '/cloud-run-source-deploy/maybloom-tracker-staging:' + args.tracker_commit[:12]
    with tempfile.TemporaryDirectory(prefix='maybloom-keyless-build-') as folder:
        source = str(Path(folder) / 'source')
        checkout_source(args.tracker_commit, source)
        if not (Path(source) / 'Dockerfile.tracker-staging').is_file():
            raise SetupError('The reviewed source does not contain the isolated Tracker build.')
        build_file = Path(folder) / 'build.json'
        build_file.write_text(json.dumps(build_definition(image)))
        print('Building the isolated test image. This can take several minutes.', flush=True)
        cloud('builds', 'submit', source, '--project=' + args.project,
              '--config=' + str(build_file), '--format=value(id)')
    print('Deploying the isolated keyless test Tracker.', flush=True)
    url = cloud(*deploy_arguments(args.project, identity, image, secret, version))
    print('Deployed test Tracker: ' + url)
    print('Share only the TEST Sheet as Editor with: ' + identity)
    print('Login, saved-record isolation and expiry still require hosted acceptance.')
    print('MB_TRACKER_URL has not been changed. Do not release this test URL to students.')


if __name__ == '__main__':
    try:
        main()
    except SetupError as error:
        print('Deployment stopped: ' + str(error) + '. Private values are hidden.', file=sys.stderr)
        sys.exit(1)
    except (KeyError, ValueError, OSError):
        print('Deployment stopped: configuration or local command error. Private values are hidden.', file=sys.stderr)
        sys.exit(1)

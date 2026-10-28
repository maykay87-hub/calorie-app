"""Prepare private Streamlit staging configuration in the owner's Cloud Shell.

No private data is printed. --apply creates a dedicated Sheets service identity
and stores its key and a separate staging coach password in Secret Manager.
Only the owner pastes the resulting TOML into the private staging app settings.
Never upload the generated file to chat, GitHub or a shared folder.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
from urllib.parse import urlparse


class SetupError(Exception):
    pass


def cloud(*args, data=None, missing=False):
    result = subprocess.run(['gcloud', *args, '--quiet'], input=data, capture_output=True, text=True)
    if result.returncode:
        if missing and 'NOT_FOUND' in result.stderr:
            return None
        raise SetupError('Cloud operation failed. Check the active account and resource permissions.')
    return result.stdout.strip()


def private_secret(project, name, create):
    found = cloud('secrets', 'describe', name, '--project=' + project, '--format=json', missing=True)
    if found is not None:
        return cloud('secrets', 'versions', 'access', 'latest', '--secret=' + name, '--project=' + project)
    value = create()
    cloud('secrets', 'create', name, '--project=' + project, '--replication-policy=automatic',
          '--data-file=-', data=value)
    return value


def sheet_key(project, email):
    with tempfile.TemporaryDirectory(prefix='maybloom-key-') as folder:
        filename = str(Path(folder) / 'key.json')
        cloud('iam', 'service-accounts', 'keys', 'create', filename, '--iam-account=' + email,
              '--project=' + project, '--key-file-type=json')
        return Path(filename).read_text()


def service_connection(service):
    container = service['spec']['template']['spec']['containers'][0]
    env = {item['name']: item for item in container.get('env', [])}
    if env.get('MB_STRIPE_LIVE', {}).get('value') != 'false':
        raise SetupError('Only an explicitly configured Stripe sandbox service is allowed.')
    origin = env.get('MB_PUBLIC_URL', {}).get('value', '').rstrip('/')
    u = urlparse(origin)
    if (u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.run.app')
            or u.username or u.password or u.port or u.path or u.query or u.fragment):
        raise SetupError('Expected the existing Cloud Run HTTPS origin.')
    reference = env.get('MB_BRIDGE_KEY', {}).get('valueFrom', {}).get('secretKeyRef', {})
    if not reference.get('name') or '/' in reference['name'] or not reference.get('key'):
        raise SetupError('An existing same-project bridge Secret Manager reference is required.')
    return origin, reference


def configuration(test_sheet, production_sheet, origin, bridge, account, admin_password):
    if test_sheet == production_sheet:
        raise SetupError('The test and student spreadsheets must be different.')
    if len(bridge) < 32 or len(admin_password) < 32:
        raise SetupError('Independent strong private credentials are required.')
    if account.get('type') != 'service_account' or not account.get('private_key'):
        raise SetupError('Expected a dedicated Sheets service-account credential.')
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['# PRIVATE: paste only into may-bloom-lab Streamlit Secrets.',
             '# The production ID is an isolation guard; staging opens only its test ID.',
             'staging_spreadsheet_id = ' + quote(test_sheet),
             'production_spreadsheet_id = ' + quote(production_sheet), '', '[passwords]',
             'admin = ' + quote(admin_password), '', '[membership_service]', 'enabled = true',
             'legacy_link_enabled = false', 'url = ' + quote(origin), 'bridge_key = ' + quote(bridge),
             '', '[service_account]']
    for key, value in account.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or not isinstance(value, str):
            raise SetupError('Unexpected credential format.')
        lines.append(key + ' = ' + quote(value))
    return '\n'.join(lines) + '\n'


def write_private(filename, content):
    path = Path(filename)
    fd, temporary = tempfile.mkstemp(prefix='.maybloom-private-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--test-sheet', required=True)
    parser.add_argument('--production-sheet', required=True)
    parser.add_argument('--output', default='/tmp/maybloom-tracker-private.toml')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,62}', args.project):
        raise SetupError('Invalid project identifier.')
    if (any(not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', s) for s in [args.test_sheet, args.production_sheet])
            or args.test_sheet == args.production_sheet):
        raise SetupError('Supply distinct valid test and student spreadsheet identifiers.')
    service = json.loads(cloud('run', 'services', 'describe', 'maybloom-member-staging',
                              '--project=' + args.project, '--region=asia-southeast1', '--format=json'))
    origin, reference = service_connection(service)
    if not args.apply:
        print('Preflight OK. Apply creates/reuses a dedicated staging Sheets identity and two private secrets,')
        print('and writes one owner-only local TOML file. It does not share Sheets or change Streamlit.')
        return
    cloud('services', 'enable', 'iam.googleapis.com', 'sheets.googleapis.com', 'drive.googleapis.com',
          '--project=' + args.project)
    email = 'maybloom-tracker-staging@' + args.project + '.iam.gserviceaccount.com'
    identity = cloud('iam', 'service-accounts', 'describe', email, '--project=' + args.project,
                     '--format=json', missing=True)
    if identity is None:
        cloud('iam', 'service-accounts', 'create', 'maybloom-tracker-staging', '--project=' + args.project,
              '--display-name=May Bloom isolated Tracker staging')
    credential = json.loads(private_secret(args.project, 'maybloom-tracker-staging-sheets-key',
                                          lambda: sheet_key(args.project, email)))
    if credential.get('client_email') != email:
        raise SetupError('The saved Sheets credential belongs to a different identity.')
    admin_password = private_secret(args.project, 'maybloom-tracker-staging-admin-password',
                                    lambda: secrets.token_urlsafe(32))
    bridge = cloud('secrets', 'versions', 'access', reference['key'], '--secret=' + reference['name'],
                   '--project=' + args.project)
    write_private(args.output, configuration(args.test_sheet, args.production_sheet, origin,
                                             bridge, credential, admin_password))
    print('Prepared: ' + args.output)
    print('Share only the TEST Sheet as Editor with: ' + email)
    print('Paste the private file only into may-bloom-lab Secrets. Keep it out of chat and GitHub.')


if __name__ == '__main__':
    try:
        main()
    except (SetupError, KeyError, ValueError, OSError):
        print('Preparation stopped. Check sandbox resources, API permissions and local output path; private values are hidden.', file=sys.stderr)
        sys.exit(1)

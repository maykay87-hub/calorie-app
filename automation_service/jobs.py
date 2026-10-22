"""Optional event wakeups; the encrypted DB outbox remains authoritative.

Task names contain hashed event identities, without emails, activation tokens,
medical records or Stripe payloads. Worker authentication remains required.
"""
import base64
from .security import digest


class JobDispatcher:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client

    def enqueue(self, event_key):
        queue = self.settings.task_queue
        if not queue:
            return False
        if self.client is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            self.client = AuthorizedSession(credentials)
        task = {
            'name': queue + '/tasks/mb-' + digest(event_key),
            'dispatchDeadline': '600s',
            'httpRequest': {
                'httpMethod': 'POST',
                'url': self.settings.public_url.rstrip('/') + '/admin/run-jobs',
                'headers': {'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + self.settings.admin_key},
                'body': base64.b64encode(b'{}').decode(),
            },
        }
        response = self.client.post('https://cloudtasks.googleapis.com/v2/' + queue + '/tasks',
                                    json={'task': task}, timeout=5)
        if response.status_code == 409:
            return False
        if not 200 <= response.status_code < 300:
            raise RuntimeError('Job dispatch unavailable.')
        return True

"""No production credentials, account IDs or price IDs are stored in source."""
from dataclasses import dataclass, field
import json
import os
import re
from urllib.parse import urlparse

PLANS = {
    'tracker-monthly': {'amount': 4800, 'months': 0, 'days': 0, 'credits': 0},
    'consultation-initial': {'amount': 19900, 'months': 0, 'days': 7, 'credits': 1},
    'consultation-three-months': {'amount': 69900, 'months': 3, 'days': 0, 'credits': 3},
    'consultation-six-months': {'amount': 99900, 'months': 6, 'days': 0, 'credits': 6},
}

@dataclass
class Settings:
    database_url: str
    encryption_key: str
    admin_key: str
    bridge_key: str
    webhook_secret: str
    public_url: str = 'http://127.0.0.1:8080'
    tracker_url: str = ''
    billing_portal_url: str = ''
    stripe_key: str = ''
    live: bool = False
    production: bool = False
    release_reviewed: bool = False
    booking_enabled: bool = False
    legacy_link_enabled: bool = False
    price_plans: dict = field(default_factory=dict)
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    mail_from: str = ''
    coach_email: str = ''
    package_start_policy: str = 'activation'
    booking_lead_seconds: int = 86400
    task_queue: str = ''
    renewal_enabled: bool = False

    def validate(self):
        if self.task_queue and (not re.fullmatch(r'projects/[a-zA-Z0-9_-]+/locations/[a-z0-9-]+/queues/[a-zA-Z0-9_-]+', self.task_queue)
                               or not self.public_url.startswith('https://')):
            raise ValueError('Job dispatch requires a Cloud Tasks queue path and HTTPS service origin.')
        if any(len(v) < 32 for v in [self.admin_key, self.bridge_key, self.webhook_secret]):
            raise ValueError('Configure distinct strong server keys (at least 32 characters).')
        if len({self.admin_key,self.bridge_key,self.webhook_secret})!=3:
            raise ValueError('Admin, Tracker and webhook keys must be distinct.')
        if self.package_start_policy not in {'activation', 'payment'}:
            raise ValueError('Choose activation or payment for package access start.')
        if not set(self.price_plans.values()) <= PLANS.keys():
            raise ValueError('Unrecognized price mapping.')
        if self.production:
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires durable PostgreSQL, not a container SQLite file.')
            public=urlparse(self.public_url)
            if (public.scheme != 'https' or not public.netloc or public.username or public.password
                    or public.path not in {'','/'} or public.query or public.fragment):
                raise ValueError('Production requires an HTTPS public URL.')
            if self.live and not self.release_reviewed:
                raise ValueError('Live fulfillment is locked until release review is recorded.')
            if set(self.price_plans.values()) != PLANS.keys() or len(self.price_plans) != 4:
                raise ValueError('Configure exactly four approved Stripe prices.')
            if not all([self.stripe_key, self.smtp_host, self.smtp_user, self.smtp_password, self.mail_from,self.coach_email]):
                raise ValueError('Stripe and transactional email must be configured before deployment.')

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.environ['MB_DATABASE_URL'], encryption_key=os.environ['MB_ENCRYPTION_KEY'],
            admin_key=os.environ['MB_ADMIN_KEY'], bridge_key=os.environ['MB_BRIDGE_KEY'],
            webhook_secret=os.environ['STRIPE_WEBHOOK_SECRET'], stripe_key=os.getenv('STRIPE_SECRET_KEY',''),
            public_url=os.getenv('MB_PUBLIC_URL','http://127.0.0.1:8080').rstrip('/'),
            tracker_url=os.getenv('MB_TRACKER_URL',''), billing_portal_url=os.getenv('MB_BILLING_PORTAL_URL',''),
            live=os.getenv('MB_STRIPE_LIVE') == 'true', production=os.getenv('MB_ENV') == 'production',
            release_reviewed=os.getenv('MB_RELEASE_REVIEWED') == 'true',
            booking_enabled=os.getenv('MB_BOOKING_ENABLED') == 'true',
            legacy_link_enabled=os.getenv('MB_LEGACY_LINK_ENABLED') == 'true',
            price_plans=json.loads(os.getenv('MB_STRIPE_PRICE_PLANS','{}')),
            smtp_host=os.getenv('MB_SMTP_HOST',''), smtp_port=int(os.getenv('MB_SMTP_PORT','587')),
            smtp_user=os.getenv('MB_SMTP_USER',''), smtp_password=os.getenv('MB_SMTP_PASSWORD',''),
            mail_from=os.getenv('MB_MAIL_FROM',''), package_start_policy=os.getenv('MB_PACKAGE_START','activation'),
            coach_email=os.getenv('MB_COACH_EMAIL',''),
            booking_lead_seconds=int(os.getenv('MB_BOOKING_LEAD_SECONDS','86400')),
            task_queue=os.getenv('MB_TASK_QUEUE',''),
            renewal_enabled=os.getenv('MB_RENEWAL_ENABLED') == 'true',
        )

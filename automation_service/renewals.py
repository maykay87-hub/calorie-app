"""Opt-in continuation after existing paid access; never a public acquisition link."""
from uuid import uuid4
from urllib.parse import urlsplit
from .service import RuleError
from .store import customers, grants, subscriptions, renewals, one, rows


class RenewalService:
    def __init__(self, service, gateway):
        self.service, self.gateway = service, gateway

    def _status(self, c, account):
        s = self.service
        if not s.settings.renewal_enabled:
            return {'eligible':False, 'reason':'not_open'}
        history = rows(c, grants, grants.c.account_id == account['id'], grants.c.revoked == False)
        if not history:
            return {'eligible':False, 'reason':'no_paid_history'}
        # Preserve paid, future and not-yet-started rights. Do not charge for overlap.
        for grant in history:
            end=grant['ends_at']
            if grant['subscription_id']:
                state=one(c, subscriptions, subscriptions.c.id == grant['subscription_id'])
                if state and state['cap_at'] is not None and end is not None:
                    end=min(end,state['cap_at'])
            if grant['starts_at'] is None or end is None or end > s.now():
                return {'eligible':False, 'reason':'existing_access'}
        return {'eligible':True, 'reason':'available'}

    def status(self, token):
        with self.service.store.read() as c:
            return self._status(c, self.service.account_for(c, token))

    def checkout(self, token, agreed):
        if agreed is not True:
            raise RuleError('请先确认月订阅安排。 Confirm the monthly subscription terms.')
        s = self.service
        with s.store.write() as c:
            account = s.account_for(c, token)
            if not self._status(c, account)['eligible']:
                raise RuleError('请先核对已有服务，避免重复付费。 Check existing access before renewing.',403)
            if not s._rate(c, account['id'], 'renewal', 8):
                raise RuleError('请稍后再试。 Please retry later.',429)
            attempt = one(c, renewals, renewals.c.account_id == account['id'])
            if not attempt or attempt['expires_at'] <= s.now():
                data = dict(account_id=account['id'], request_key=uuid4().hex,
                            created_at=s.now(), expires_at=s.now()+3600, checkout_id=None, checkout_url=None, customer_id=None)
                if attempt:
                    c.execute(renewals.update().where(renewals.c.account_id == account['id']).values(**data))
                else:
                    c.execute(renewals.insert().values(**data))
                attempt = data
            context = dict(attempt, email=account['email'],
                           customer_ids=[r['id'] for r in rows(c, customers, customers.c.account_id == account['id'])])
        # No DB lock during network I/O. Concurrent requests reuse one Stripe
        # idempotency key and the same absolute expiry, including after a crash.
        result = self.gateway.renewal_checkout(context)
        url = urlsplit(result.get('url',''))
        if (url.scheme != 'https' or url.hostname != 'checkout.stripe.com' or url.port
                or url.username or url.password or not result.get('id')
                or result.get('expires_at') != context['expires_at']):
            raise ValueError('Unexpected renewal destination.')
        with s.store.write() as c:
            account = s.account_for(c, token)
            current = one(c, renewals, renewals.c.account_id == account['id'])
            if not current or current['request_key'] != context['request_key']:
                raise RuleError('链接已过期，请重试。 Checkout expired; retry.',409)
            identity = one(c, customers, customers.c.id == result['customer_id'])
            if identity and identity['account_id'] != account['id']:
                raise RuleError('请联系 May 核对账号。 Account review required.',409)
            if not identity:
                c.execute(customers.insert().values(id=result['customer_id'], account_id=account['id']))
            c.execute(renewals.update().where(renewals.c.account_id == account['id']).values(
                checkout_id=result['id'], checkout_url=result['url'], customer_id=result['customer_id']))
        return {'url':result['url']}

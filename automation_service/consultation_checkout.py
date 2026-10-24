"""Slot-first one-time checkout. All grants/bookings still require a paid webhook.

An elapsed local timer never proves that a payment failed. Holds are released
only after Stripe confirms expiration, including after timeouts/crashes.
"""
from urllib.parse import urlsplit
from uuid import uuid4
from .availability import candidate_slots
from .config import PLANS
from .security import digest, email_key
from .service import RuleError
from .store import consultation_holds as holds, slots, one, rows

APPROVED_STARTS = frozenset(int(start.timestamp()) for start, _ in candidate_slots())


class ConsultationCheckout:
    def __init__(self, service, gateway):
        self.service, self.gateway = service, gateway

    def _enabled(self):
        if not self.service.settings.consultation_checkout_enabled:
            raise RuleError('线上预约付款尚未开放。 Online booking payment is not open.', 503)

    def available(self):
        if not self.service.settings.consultation_checkout_enabled:
            return {'enabled':False, 'slots':[]}
        s = self.service
        with s.store.read() as c:
            available = sorted([dict(id=slot['id'], starts_at=slot['starts_at'], ends_at=slot['ends_at'])
                for slot in rows(c, slots, slots.c.status=='available',
                                 slots.c.starts_at>=s.now()+s.settings.booking_lead_seconds)
                if slot['starts_at'] in APPROVED_STARTS], key=lambda slot:slot['starts_at'])
        return {'enabled':True, 'slots':available, 'timezone':'Asia/Kuala_Lumpur',
                'plans':{key:dict(amount=value['amount'], credits=value['credits'])
                         for key, value in PLANS.items() if key!='tracker-monthly'}}

    def checkout(self, owner, email, plan, slot_id, request_id):
        self._enabled()
        s = self.service
        email = email_key(email)
        if plan not in PLANS or plan=='tracker-monthly':
            raise RuleError('请选择咨询配套。 Choose a consultation package.')
        owner_hash = digest(owner)
        with s.store.write() as c:
            previous = one(c, holds, holds.c.owner_hash==owner_hash, holds.c.request_id==request_id)
            if previous:
                if (previous['email'],previous['plan'],previous['slot_id'])!=(email,plan,slot_id):
                    raise RuleError('请重新选择时段。 Request already used for another booking.',409)
                if previous['status']!='pending' or previous['expires_at']<=s.now():
                    raise RuleError('请先查看付款状态，再重新选择。 Check payment status before retrying.',409)
                context = dict(previous)
            else:
                # Committed accounting is handled by the HTTP boundary before this transaction.
                if one(c, holds, holds.c.owner_hash==owner_hash, holds.c.status=='pending'):
                    raise RuleError('已有待处理付款，请完成或等待该付款结束。 A checkout is already pending.',409)
                slot = one(c, slots, slots.c.id==slot_id)
                if (not slot or slot['status']!='available' or slot['starts_at'] not in APPROVED_STARTS
                        or slot['starts_at']<s.now()+s.settings.booking_lead_seconds):
                    raise RuleError('时段已不可用，请重选。 Slot unavailable.',409)
                context = dict(id=uuid4().hex, slot_id=slot_id, owner_hash=owner_hash, request_id=request_id,
                    email=email, plan=plan, created_at=s.now(), expires_at=s.now()+3600,
                    status='pending', checkout_id=None, checkout_url=None, booking_id=None)
                c.execute(holds.insert().values(**context))
                c.execute(slots.update().where(slots.c.id==slot_id).values(status='held'))
        # Preserve the hold on uncertain network errors. Retries use the same Stripe key.
        result = self.gateway.consultation_checkout(context)
        url = urlsplit(result.get('url') or '')
        if (url.scheme!='https' or url.hostname!='checkout.stripe.com' or url.port or url.username
                or url.password or not result.get('id') or result.get('expires_at')!=context['expires_at']):
            raise ValueError('Unexpected checkout destination or expiration.')
        with s.store.write() as c:
            current = one(c, holds, holds.c.id==context['id'])
            if current['checkout_id'] and current['checkout_id']!=result['id']:
                raise RuleError('付款状态需要核对。 Payment review required.',409)
            # A webhook can win the race; do not restore pending after it confirms/expires.
            c.execute(holds.update().where(holds.c.id==context['id']).values(
                checkout_id=result['id'], checkout_url=result['url']))
        return {'url':result['url'], 'hold_id':context['id']}

    def status(self, owner):
        with self.service.store.read() as c:
            owned = sorted(rows(c, holds, holds.c.owner_hash==digest(owner)), key=lambda row:row['created_at'])
            if not owned: return {'status':'none'}
            hold = owned[-1]
            slot = one(c, slots, slots.c.id==hold['slot_id'])
            return {'status':hold['status'], 'starts_at':slot['starts_at'], 'ends_at':slot['ends_at'],
                    'expires_at':hold['expires_at'],
                    'checkout_url':hold['checkout_url'] if hold['status']=='pending' and hold['expires_at']>self.service.now() else None}

    def resume(self, owner):
        self._enabled()
        with self.service.store.read() as c:
            pending=rows(c,holds,holds.c.owner_hash==digest(owner),holds.c.status=='pending')
            if not pending: raise RuleError('没有待处理的付款。 No pending checkout.',404)
            hold=max(pending,key=lambda row:row['created_at'])
        return self.checkout(owner,hold['email'],hold['plan'],hold['slot_id'],hold['request_id'])

    def expire(self, canonical):
        """Input is a session re-read from Stripe, never webhook body/URL values."""
        if canonical.get('status')!='expired': return
        s = self.service
        with s.store.write() as c:
            hold = one(c, holds, holds.c.id==canonical.get('hold_id'))
            if not hold or hold['status']!='pending': return
            if (hold['checkout_id'] and hold['checkout_id']!=canonical['id']) or canonical.get('expires_at')!=hold['expires_at']:
                raise ValueError('Expired session does not match its hold.')
            c.execute(holds.update().where(holds.c.id==hold['id']).values(status='expired',checkout_id=canonical['id']))
            slot = one(c, slots, slots.c.id==hold['slot_id'])
            if slot and slot['status']=='held':
                c.execute(slots.update().where(slots.c.id==slot['id']).values(status='available'))

    def sweep(self):
        s = self.service
        with s.store.read() as c:
            pending = [dict(h) for h in rows(c, holds, holds.c.status=='pending', holds.c.expires_at<=s.now())]
        for hold in pending:
            if not hold['checkout_id']:
                s.flag('hold:'+hold['id'], 'checkout_creation_uncertain')
                continue  # Unknown external result must not release a potentially paid slot.
            canonical = self.gateway.consultation_state(hold['checkout_id'])
            self.expire(canonical)
            if canonical.get('status')=='complete':
                s.flag('hold-reconcile:'+hold['id'],'checkout_awaiting_paid_webhook')

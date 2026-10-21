"""Atomic fulfillment, identity, entitlements, booking credits and email outbox."""
import calendar
from datetime import datetime, timezone
import json
import secrets
import time
from uuid import uuid4
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet
from sqlalchemy import select, delete, update
from .config import PLANS
from .security import email_key, digest, password_hash, password_matches, random_token
from .store import (accounts, customers, grants, subscriptions, events, tokens, outbox,
                    slots, bookings, limits, issues, one, rows)

class RuleError(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status

def add_months(epoch, months):
    d = datetime.fromtimestamp(epoch, timezone.utc)
    month = d.year * 12 + d.month - 1 + months
    year, month = divmod(month,12); month += 1
    return int(d.replace(year=year, month=month, day=min(d.day,calendar.monthrange(year,month)[1])).timestamp())

class Service:
    def __init__(self, store, settings, clock=time.time):
        settings.validate()
        self.store, self.settings, self.clock = store, settings, clock
        self.cipher = Fernet(settings.encryption_key.encode())

    def now(self): return int(self.clock())

    def _queue(self, c, key, payload):
        if not one(c,outbox,outbox.c.id==key):
            c.execute(outbox.insert().values(id=key,payload=self.cipher.encrypt(json.dumps(payload).encode()).decode(),
                                            status='pending',created_at=self.now()))

    def _activation(self,c,account):
        # A second delivery gets a separate one-time token, without invalidating a queued first email.
        now = self.now()
        token = random_token()
        key = f"activation:{account['id']}:{digest(token)[:16]}"
        c.execute(tokens.insert().values(hash=digest(token), account_id=account['id'],kind='activation',expires_at=now+3600))
        self._queue(c,key,{'to':account['email'],'kind':'activation',
            'subject':'May Bloom · 开通或恢复账号 / Activate your account',
            'body':f"请使用下方链接设置密码（1小时内有效）。已有账号可用此链接恢复密码。\nSet or reset your password using this link, valid for 1 hour.\n\n{self.settings.public_url}/#activate={token}\n\n如果你没有申请，可忽略此邮件。If you did not request this, ignore this email."})

    def _account(self,c,email,customer_id=None):
        if customer_id:
            identity=one(c,customers,customers.c.id==customer_id)
            if identity: return one(c,accounts,accounts.c.id==identity['account_id'])
        email=email_key(email)
        account=one(c,accounts,accounts.c.email==email)
        if not account:
            aid=uuid4().hex
            c.execute(accounts.insert().values(id=aid,email=email,username='mb_'+aid,password_hash=None,
                                               verified_at=None,created_at=self.now(),tracker_used=False))
            account=one(c,accounts,accounts.c.id==aid)
        if customer_id: c.execute(customers.insert().values(id=customer_id,account_id=account['id']))
        return account

    def _rate(self,c,identity,action,maximum=8):
        key=digest(action+':'+identity)
        row=one(c,limits,limits.c.key==key); now=self.now(); window=now//900
        if row and row['window']==window:
            if row['count'] >= maximum: return False
            c.execute(limits.update().where(limits.c.key==key).values(count=row['count']+1))
        elif row: c.execute(limits.update().where(limits.c.key==key).values(window=window,count=1))
        else: c.execute(limits.insert().values(key=key,window=window,count=1))
        return True

    def request_activation(self,email):
        try: email=email_key(email)
        except ValueError: return
        with self.store.write() as c:
            if not self._rate(c,email,'activation',4): return
            account=one(c,accounts,accounts.c.email==email)
            coach=email==self.settings.coach_email.strip().casefold() and bool(self.settings.coach_email)
            if coach and not account: account=self._account(c,email)
            if account and (coach or one(c,grants,grants.c.account_id==account['id'])): self._activation(c,account)

    def activate(self,token,password):
        with self.store.write() as c:
            item=one(c,tokens,tokens.c.hash==digest(token),tokens.c.kind=='activation')
            if not item or item['expires_at'] <= self.now(): raise RuleError('链接已失效，请重新申请。 Link expired; request another.')
            encoded=password_hash(password)
            aid=item['account_id']
            c.execute(accounts.update().where(accounts.c.id==aid).values(password_hash=encoded,verified_at=self.now()))
            c.execute(delete(tokens).where(tokens.c.account_id==aid))
            for grant in rows(c,grants,grants.c.account_id==aid,grants.c.starts_at.is_(None)):
                self._start(c,grant,self.now())
            return self._session(c,aid)

    def _session(self,c,aid):
        token=random_token()
        c.execute(tokens.insert().values(hash=digest(token),account_id=aid,kind='session',expires_at=self.now()+86400))
        return token

    def login(self,email,password):
        try: email=email_key(email)
        except ValueError: email='invalid@example.invalid'
        # Commit rate accounting even for a failed password.
        with self.store.write() as c:
            allowed=self._rate(c,email,'login')
            account=one(c,accounts,accounts.c.email==email)
            matched=password_matches(password,account['password_hash'] if account else None)
            token=self._session(c,account['id']) if allowed and matched and account['verified_at'] else None
        if not allowed: raise RuleError('请稍后再试。 Please try later.',429)
        if not token: raise RuleError('邮箱或密码不正确。 Incorrect email or password.',401)
        return token

    def account_for(self,c,token):
        item=one(c,tokens,tokens.c.hash==digest(token),tokens.c.kind=='session')
        if not item or item['expires_at'] <= self.now(): raise RuleError('请重新登入。 Please sign in.',401)
        account=one(c,accounts,accounts.c.id==item['account_id'])
        if not account or not account['verified_at']: raise RuleError('请先验证邮箱。 Verify your email.',401)
        return account

    def logout(self,token):
        with self.store.write() as c: c.execute(delete(tokens).where(tokens.c.hash==digest(token),tokens.c.kind=='session'))

    def tracker_session(self,token):
        with self.store.write() as c:
            account=self.account_for(c,token)
            c.execute(accounts.update().where(accounts.c.id==account['id']).values(tracker_used=True))
        return self.me(token)

    def link_legacy(self,token,username):
        """Only the trusted Tracker bridge calls this after its old-account password check."""
        if not self.settings.legacy_link_enabled:
            raise RuleError('原账号权益需先由 May 核对；原账号仍可使用。 Legacy entitlements require a reviewed migration.',503)
        if (not isinstance(username,str) or not 1<=len(username)<=100 or username.strip()!=username
                or not username.isprintable() or username.casefold()=='admin'):
            raise RuleError('Invalid legacy account identity.')
        with self.store.write() as c:
            account=self.account_for(c,token)
            if account['username']==username: return username
            if not self._active(c,account['id']): raise RuleError('请先确认会员权限已生效。 Membership is not active.',403)
            if account['tracker_used'] or not account['username'].startswith('mb_'):
                raise RuleError('账号已使用或已关联，请联系 May 合并检查。 Account already used; a reviewed migration is required.',409)
            if one(c,accounts,accounts.c.username==username): raise RuleError('该原账号已关联，请联系 May。 Account already linked.',409)
            c.execute(accounts.update().where(accounts.c.id==account['id']).values(username=username))
        return username

    def legacy_login(self,username):
        # Caller is the trusted Tracker server AFTER checking the existing password.
        with self.store.write() as c:
            account=one(c,accounts,accounts.c.username==username)
            if not account: return {'managed':False}
            if username.casefold()=='admin': raise RuleError('Reserved identity.',403)
            token=self._session(c,account['id'])
        return {'managed':True,'token':token,**self.me(token)}

    def _start(self,c,grant,start):
        plan=PLANS[grant['plan']]
        end=add_months(start,plan['months']) if plan['months'] else start+plan['days']*86400
        c.execute(grants.update().where(grants.c.id==grant['id']).values(starts_at=start,ends_at=end))

    def _active(self,c,aid):
        active=[]; now=self.now()
        for grant in rows(c,grants,grants.c.account_id==aid,grants.c.revoked==False):
            start,end=grant['starts_at'],grant['ends_at']
            if grant['subscription_id']:
                sub=one(c,subscriptions,subscriptions.c.id==grant['subscription_id'])
                if sub and sub['cap_at'] is not None: end=min(end,sub['cap_at'])
            if start is not None and end is not None and start<=now<end:
                active.append(dict(grant,ends_at=end))
        return active

    def me(self,token):
        with self.store.read() as c:
            account=self.account_for(c,token); active=self._active(c,account['id'])
            appointments=[]
            for b in rows(c,bookings,bookings.c.account_id==account['id']):
                slot=one(c,slots,slots.c.id==b['slot_id'])
                appointments.append({'id':b['id'],'starts_at':slot['starts_at'],'ends_at':slot['ends_at']})
            return {'username':account['username'],'display_name':account['email'].split('@')[0],'active':bool(active),
                    'is_coach':account['email']==self.settings.coach_email.strip().casefold() and bool(self.settings.coach_email),
                    'ends_at':max((g['ends_at'] for g in active),default=None),
                    'credits':sum(g['credits'] for g in active),
                    'plans':sorted(set(g['plan'] for g in active)),
                    'appointments':sorted(appointments,key=lambda b:b['starts_at']),
                    'tracker_url':self.settings.tracker_url,'billing_portal_url':self.settings.billing_portal_url,
                    'booking_enabled':self.settings.booking_enabled}

    def fulfill(self,event_id,kind,paid):
        """Only canonical objects supplied by the verified Stripe gateway enter here."""
        with self.store.write() as c:
            if one(c,events,events.c.id==event_id): return 'duplicate'
            if paid:
                plan_id=paid['plan']
                if plan_id not in PLANS: raise RuleError('Unknown approved plan.')
                account=self._account(c,paid['email'],paid.get('customer_id'))
                if not one(c,grants,grants.c.id==paid['source_id']):
                    data=dict(id=paid['source_id'],account_id=account['id'],plan=plan_id,
                              subscription_id=paid.get('subscription_id'),payment_intent=paid.get('payment_intent'),
                              starts_at=paid.get('starts_at'),ends_at=paid.get('ends_at'),
                              paid_at=paid['paid_at'],credits=PLANS[plan_id]['credits'],revoked=False)
                    c.execute(grants.insert().values(**data))
                    if plan_id!='tracker-monthly' and (account['verified_at'] or self.settings.package_start_policy=='payment'):
                        self._start(c,data,paid['paid_at'] if self.settings.package_start_policy=='payment' else self.now())
                    self._queue(c,'purchase:'+paid['source_id'],{'to':account['email'],'kind':'purchase',
                        'subject':'May Bloom · 服务已记录 / Your service is ready',
                        'body':f"已记录你的方案：{plan_id}。\nYour service has been recorded.\n\n登入或申请开通 / Sign in or request activation:\n{self.settings.public_url}\n\n咨询预约仅显示已开放的时段。Consultations use published availability."})
                    if not account['verified_at']: self._activation(c,account)
                if paid.get('subscription_state'):
                    self._subscription(c,paid['subscription_state'])
            c.execute(events.insert().values(id=event_id,kind=kind,processed_at=self.now()))
        return 'processed'

    def _subscription(self,c,state):
        old=one(c,subscriptions,subscriptions.c.id==state['id'])
        if old and old['event_time']>state['event_time']: return
        if old and old['cap_at'] is not None and state['cap_at'] is None: return
        if old: c.execute(subscriptions.update().where(subscriptions.c.id==state['id']).values(**state))
        else: c.execute(subscriptions.insert().values(**state))

    def reconcile_subscription(self,event_id,kind,state):
        with self.store.write() as c:
            if one(c,events,events.c.id==event_id): return 'duplicate'
            self._subscription(c,state)
            c.execute(events.insert().values(id=event_id,kind=kind,processed_at=self.now()))
        return 'processed'

    def flag(self,event_id,kind):
        # Refunds, disputes and failed-payment policy need human review; never delete diet records.
        with self.store.write() as c:
            if not one(c,issues,issues.c.id==event_id):
                c.execute(issues.insert().values(id=event_id,kind=kind,created_at=self.now()))
                if self.settings.coach_email:
                    self._queue(c,'issue:'+event_id,{'to':self.settings.coach_email,'kind':'operator_issue',
                        'subject':'May Bloom · 付款事件待检查 / Payment review needed',
                        'body':f"请在 Stripe 后台检查事件 / Review this event in Stripe:\n{kind}\n{event_id}\n\n系统没有自动退款或删除学员记录。No automatic refund or record deletion was performed."})

    def publish_slot(self,start):
        if not isinstance(start,int) or start < self.now()+self.settings.booking_lead_seconds:
            raise RuleError('预约时段必须在最短提前时间之后。 Slot is too soon.')
        end=start+2700
        with self.store.write() as c:
            if one(c,slots,slots.c.status!='closed',slots.c.starts_at<end+900,slots.c.ends_at+900>start):
                raise RuleError('时段冲突（包含15分钟缓冲）。 Slot overlaps another slot or its 15-minute buffer.',409)
            previous=one(c,slots,slots.c.starts_at==start,slots.c.status=='closed')
            if previous:
                c.execute(slots.update().where(slots.c.id==previous['id']).values(status='available'))
                return previous['id']
            sid=uuid4().hex
            c.execute(slots.insert().values(id=sid,starts_at=start,ends_at=end,status='available'))
        return sid

    def close_slot(self,slot_id):
        with self.store.write() as c:
            slot=one(c,slots,slots.c.id==slot_id)
            if not slot: raise RuleError('Slot not found.',404)
            if slot['status']=='booked': raise RuleError('已有预约；请先与学员确认改期。 Slot is booked; arrange the change with the member.',409)
            c.execute(slots.update().where(slots.c.id==slot_id).values(status='closed'))

    def available_slots(self,token):
        if not self.settings.booking_enabled: return []
        with self.store.read() as c:
            account=self.account_for(c,token); eligible=[g for g in self._active(c,account['id']) if g['credits']>0]
            return sorted([{'id':s['id'],'starts_at':s['starts_at'],'ends_at':s['ends_at']}
                    for s in rows(c,slots,slots.c.status=='available',slots.c.starts_at>=self.now()+self.settings.booking_lead_seconds)
                    if any(s['starts_at']<g['ends_at'] for g in eligible)],key=lambda s:s['starts_at'])

    def book(self,token,slot_id,request_id):
        if not self.settings.booking_enabled: raise RuleError('预约尚未开放。 Booking is not open.',503)
        if not request_id or len(request_id)>100: raise RuleError('A booking request ID is required.')
        with self.store.write() as c:
            account=self.account_for(c,token)
            prior=one(c,bookings,bookings.c.account_id==account['id'],bookings.c.request_id==request_id)
            if prior:
                if prior['slot_id']!=slot_id: raise RuleError('Request ID already used for a different slot.',409)
                return prior['id']
            slot=one(c,slots,slots.c.id==slot_id)
            if not slot or slot['status']!='available' or slot['starts_at']<self.now()+self.settings.booking_lead_seconds:
                raise RuleError('该时段已不可用，请重选。 Slot unavailable.',409)
            eligible=[g for g in self._active(c,account['id']) if g['credits']>0 and slot['starts_at']<g['ends_at']]
            if not eligible: raise RuleError('没有可用的咨询次数。 No eligible consultation credit.',403)
            grant=min(eligible,key=lambda g:g['ends_at']); bid=uuid4().hex
            c.execute(slots.update().where(slots.c.id==slot_id).values(status='booked'))
            c.execute(grants.update().where(grants.c.id==grant['id']).values(credits=grant['credits']-1))
            c.execute(bookings.insert().values(id=bid,slot_id=slot_id,account_id=account['id'],grant_id=grant['id'],request_id=request_id,created_at=self.now()))
            time_text=datetime.fromtimestamp(slot['starts_at'],ZoneInfo('Asia/Kuala_Lumpur')).strftime('%Y-%m-%d %H:%M MYT')
            self._queue(c,'booking:'+bid,{'to':account['email'],'kind':'booking','booking_id':bid,
                'starts_at':slot['starts_at'],'ends_at':slot['ends_at'],
                'subject':'May Bloom · 预约确认 / Consultation confirmed',
                'body':f"你的45分钟线上咨询已预约。\nYour 45-minute online consultation is booked.\n\n时间 / Time: {time_text}\n\n会员页面 / Member page:\n{self.settings.public_url}\n\n会议链接将由 May 另行提供。May will provide the meeting link separately."})
            if self.settings.coach_email:
                self._queue(c,'coach-booking:'+bid,{'to':self.settings.coach_email,'kind':'coach_booking','booking_id':bid,
                    'starts_at':slot['starts_at'],'ends_at':slot['ends_at'],
                    'subject':'May Bloom · 新咨询预约 / New consultation booking',
                    'body':f"学员 / Member: {account['email']}\n时间 / Time: {time_text}\n时长 / Duration: 45 minutes\n\n请提供线上会议链接。Please provide the meeting link."})
            return bid

    def enqueue_reminders(self):
        with self.store.write() as c:
            for b in rows(c,bookings):
                slot=one(c,slots,slots.c.id==b['slot_id']); delta=slot['starts_at']-self.now()
                if 0<delta<=86400:
                    account=one(c,accounts,accounts.c.id==b['account_id'])
                    self._queue(c,'reminder:'+b['id'],{'to':account['email'],'kind':'reminder',
                        'subject':'May Bloom · 咨询提醒 / Consultation reminder',
                        'body':f"你的咨询将在24小时内开始。Your consultation is within 24 hours.\n时间 / Time: {datetime.fromtimestamp(slot['starts_at'],ZoneInfo('Asia/Kuala_Lumpur')).strftime('%Y-%m-%d %H:%M MYT')}\n\n{self.settings.public_url}"})

    def deliver_pending(self,sender,limit=20):
        delivered=0
        for _ in range(limit):
            with self.store.write() as c:
                # A crashed sender is ambiguous: flag it rather than silently sending again.
                for msg in rows(c,outbox,outbox.c.status=='sending',outbox.c.claimed_at<self.now()-900):
                    c.execute(outbox.update().where(outbox.c.id==msg['id']).values(status='uncertain'))
                    if not one(c,issues,issues.c.id=='mail:'+msg['id']):
                        c.execute(issues.insert().values(id='mail:'+msg['id'],kind='email_delivery_uncertain',created_at=self.now()))
                msg=c.execute(select(outbox).where(outbox.c.status=='pending').order_by(outbox.c.created_at).limit(1)).mappings().first()
                if not msg: break
                c.execute(outbox.update().where(outbox.c.id==msg['id']).values(status='sending',claimed_at=self.now()))
                payload=json.loads(self.cipher.decrypt(msg['payload'].encode()))
            try: sender(msg['id'],payload)
            except Exception:
                with self.store.write() as c:
                    c.execute(outbox.update().where(outbox.c.id==msg['id']).values(status='uncertain'))
                    if not one(c,issues,issues.c.id=='mail:'+msg['id']):
                        c.execute(issues.insert().values(id='mail:'+msg['id'],kind='email_delivery_uncertain',created_at=self.now()))
            else:
                with self.store.write() as c:
                    c.execute(outbox.update().where(outbox.c.id==msg['id']).values(status='sent',sent_at=self.now()))
                delivered+=1
        return delivered

    def admin_summary(self):
        with self.store.read() as c:
            return {'accounts':[{'id':a['id'],'email':a['email'],'username':a['username'],'verified':bool(a['verified_at']),
                                  'active':bool(self._active(c,a['id']))} for a in rows(c,accounts)],
                    'memberships':[{k:g[k] for k in ['id','account_id','plan','starts_at','ends_at','credits','revoked']} for g in rows(c,grants)],
                    'appointments':[dict(b) for b in rows(c,bookings)],
                    'slots':[dict(slot) for slot in rows(c,slots)],
                    'issues':[dict(i) for i in rows(c,issues)],
                    'mail':[{k:m[k] for k in ['id','status','created_at','sent_at']} for m in rows(c,outbox)]}

    def coach_authorized(self,token):
        with self.store.read() as c:
            account=self.account_for(c,token)
            if not self.settings.coach_email or account['email']!=self.settings.coach_email.strip().casefold():
                raise RuleError('仅限教练管理。 Coach access required.',403)

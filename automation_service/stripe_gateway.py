"""Retrieve authoritative payment objects; browser redirects never grant access."""
import time
import stripe
from .config import PLANS
from .service import RuleError

def object_id(value): return value.get('id') if isinstance(value,dict) else value
def plain(value): return value if isinstance(value,dict) else value.to_dict()

class StripeGateway:
    def __init__(self,settings):
        self.settings=settings
        self.client=stripe.StripeClient(settings.stripe_key,max_network_retries=2,
                                       http_client=stripe.RequestsClient(timeout=10))

    def _mode(self,obj):
        if obj.get('livemode') is not self.settings.live: raise ValueError('Stripe environment mismatch.')

    def _plan(self,price_id):
        plan=self.settings.price_plans.get(price_id)
        if not plan: return None
        price=plain(self.client.v1.prices.retrieve(price_id))
        self._mode(price)
        if price.get('currency')!='myr' or price.get('unit_amount')!=PLANS[plan]['amount']:
            raise ValueError('Configured price does not match the approved catalogue.')
        recurring=price.get('recurring')
        if plan=='tracker-monthly':
            if not recurring or recurring.get('interval')!='month' or recurring.get('interval_count')!=1:
                raise ValueError('Expected a monthly recurring price.')
        elif recurring: raise ValueError('Consultation packages must be one-time prices.')
        return plan

    def subscription(self,sid,event_time):
        sub=plain(self.client.v1.subscriptions.retrieve(sid)); self._mode(sub)
        cap=sub.get('ended_at') if sub.get('status')=='canceled' else None
        if sub.get('status')=='canceled' and not cap: raise ValueError('Canceled subscription has no end time.')
        return {'id':sid,'cap_at':cap,'event_time':event_time}

    def invoice(self,iid,event_time):
        inv=plain(self.client.v1.invoices.retrieve(iid)); self._mode(inv)
        if inv.get('status')!='paid' or inv.get('amount_paid',0)<=0: return None
        lines=plain(self.client.v1.invoices.line_items.list(iid,{'limit':100}))
        if lines.get('has_more'): raise ValueError('Unexpected multi-page membership invoice.')
        matches=[]
        for line in lines.get('data',[]):
            price_id=(line.get('pricing') or {}).get('price_details',{}).get('price')
            if not price_id: price_id=object_id(line.get('price'))
            if self.settings.price_plans.get(price_id)!='tracker-monthly': continue
            details=(line.get('parent') or {}).get('subscription_item_details') or {}
            if line.get('proration') or details.get('proration'): continue
            if line.get('quantity')!=1 or self._plan(price_id)!='tracker-monthly':
                raise ValueError('Unexpected recurring quantity.')
            matches.append(line)
        if not matches: return None
        if len(matches)!=1: raise ValueError('Expected one membership line.')
        parent=(inv.get('parent') or {}).get('subscription_details') or {}
        sid=object_id(parent.get('subscription') or inv.get('subscription'))
        if not sid: raise ValueError('Missing subscription identity.')
        customer_id=object_id(inv.get('customer'))
        customer=plain(self.client.v1.customers.retrieve(customer_id))
        period=matches[0].get('period',{})
        start,end=period.get('start'),period.get('end')
        if not isinstance(start,int) or not isinstance(end,int) or not 0<end-start<=32*86400:
            raise ValueError('Unexpected membership period.')
        return {'source_id':'in:'+iid,'plan':'tracker-monthly','email':customer['email'],
                'customer_id':customer_id,'subscription_id':sid,'starts_at':start,'ends_at':end,
                'paid_at':(inv.get('status_transitions') or {}).get('paid_at') or event_time,
                'subscription_state':self.subscription(sid,event_time)}

    def checkout(self,sid,event_time):
        session=plain(self.client.v1.checkout.sessions.retrieve(sid,{'expand':['line_items']})); self._mode(session)
        if session.get('status')!='complete' or session.get('payment_status')!='paid': return None
        if session.get('mode')=='subscription':
            iid=object_id(session.get('invoice'))
            if not iid: raise ValueError('Paid subscription checkout is missing its invoice.')
            return self.invoice(iid,event_time)
        if session.get('mode')!='payment': return None
        lines=session.get('line_items') or {}
        if lines.get('has_more') or len(lines.get('data',[]))!=1: raise ValueError('Expected one approved product.')
        line=lines['data'][0]
        if line.get('quantity')!=1: raise ValueError('Unexpected quantity.')
        plan=self._plan(object_id(line.get('price')))
        if not plan: return None
        if plan=='tracker-monthly': raise ValueError('Monthly access requires a paid subscription invoice.')
        if session.get('amount_total',0)<=0: raise ValueError('A paid package cannot have a zero total.')
        hold_id=(session.get('metadata') or {}).get('mb_hold_id')
        if hold_id and (session.get('currency')!='myr' or session.get('amount_total')!=PLANS[plan]['amount']):
            raise ValueError('Reserved consultation total does not match the approved package.')
        return {'source_id':'cs:'+sid,'plan':plan,'hold_id':hold_id,
                'email':(session.get('customer_details') or {}).get('email') or session.get('customer_email'),
                'customer_id':object_id(session.get('customer')),
                'payment_intent':object_id(session.get('payment_intent')),'paid_at':event_time}

    def consultation_checkout(self, context):
        prices=[price for price,plan in self.settings.price_plans.items() if plan==context['plan']]
        if len(prices)!=1 or self._plan(prices[0])!=context['plan']:
            raise ValueError('One approved consultation price is required.')
        if context.get('checkout_id'):
            session=plain(self.client.v1.checkout.sessions.retrieve(context['checkout_id']))
        else:
            session=plain(self.client.v1.checkout.sessions.create({
                'mode':'payment', 'customer_email':context['email'], 'customer_creation':'always',
                'line_items':[{'price':prices[0],'quantity':1}],
                # Start with immediate card payments; delayed methods need separate release policy.
                'payment_method_types':['card'], 'expires_at':context['expires_at'],
                'metadata':{'mb_hold_id':context['id']},
                'success_url':self.settings.public_url+'/consultation?payment=returned',
                'cancel_url':self.settings.public_url+'/consultation?payment=cancelled',
                'phone_number_collection':{'enabled':True},
            },options={'idempotency_key':'mb-consultation-'+context['id']}))
        self._mode(session)
        if (session.get('status')!='open' or session.get('mode')!='payment'
                or (session.get('metadata') or {}).get('mb_hold_id')!=context['id']):
            raise RuleError('请查看付款状态。 Please check your payment status.',409)
        return {'id':session['id'],'url':session.get('url'),'expires_at':session.get('expires_at')}

    def consultation_state(self, sid):
        session=plain(self.client.v1.checkout.sessions.retrieve(sid)); self._mode(session)
        return {'id':session['id'],'status':session.get('status'),
                'hold_id':(session.get('metadata') or {}).get('mb_hold_id'),
                'expires_at':session.get('expires_at')}

    def renewal_checkout(self, context):
        prices = [p for p, plan in self.settings.price_plans.items() if plan == 'tracker-monthly']
        if len(prices) != 1 or self._plan(prices[0]) != 'tracker-monthly':
            raise ValueError('One approved monthly price is required.')
        listed = plain(self.client.v1.customers.list({'email':context['email'], 'limit':100}))
        if listed.get('has_more'):
            raise RuleError('请联系 May 核对账号。 Account review required.',409)
        identities = set(context['customer_ids']) | {v['id'] for v in listed.get('data',[])}
        if len(identities) > 10:
            raise RuleError('请联系 May 核对账号。 Account review required.',409)
        for cid in sorted(identities):
            customer = plain(self.client.v1.customers.retrieve(cid)); self._mode(customer)
            if customer.get('deleted') or (customer.get('email') or '').strip().casefold() != context['email']:
                raise RuleError('请联系 May 核对邮箱。 Email review required.',409)
            subscriptions = plain(self.client.v1.subscriptions.list({'customer':cid, 'status':'all', 'limit':100}))
            if subscriptions.get('has_more') or any(v.get('status') not in {'canceled','incomplete_expired'} for v in subscriptions.get('data',[])):
                raise RuleError('已有订阅或待处理付款，请先查看账单。 Check your existing subscription or pending payment.',409)
        if context.get('customer_id'):
            if context['customer_id'] not in identities:
                raise RuleError('请联系 May 核对账号。 Account review required.',409)
            cid = context['customer_id']
        elif identities:
            cid = sorted(identities)[0]
        else:
            customer = plain(self.client.v1.customers.create({'email':context['email']},
                options={'idempotency_key':'mb-renewal-customer-'+context['account_id']}))
            self._mode(customer); cid = customer['id']
        if context.get('checkout_id'):
            session = plain(self.client.v1.checkout.sessions.retrieve(context['checkout_id']))
        else:
            session = plain(self.client.v1.checkout.sessions.create({
                'mode':'subscription', 'customer':cid,
                'line_items':[{'price':prices[0], 'quantity':1}],
                'success_url':self.settings.public_url+'/?renewal=complete',
                'cancel_url':self.settings.public_url+'/?renewal=cancelled',
                'expires_at':context['expires_at'],
            }, options={'idempotency_key':'mb-renewal-'+context['request_key']}))
        self._mode(session)
        if session.get('status') != 'open' or object_id(session.get('customer')) != cid:
            raise RuleError('付款正在处理或链接已结束，请查看账单。 Check payment status before retrying.',409)
        return {'id':session['id'], 'url':session.get('url'), 'customer_id':cid,
                'expires_at':session.get('expires_at')}

"""Retrieve authoritative payment objects; browser redirects never grant access."""
import time
import stripe
from .config import PLANS

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
        return {'source_id':'cs:'+sid,'plan':plan,
                'email':(session.get('customer_details') or {}).get('email') or session.get('customer_email'),
                'customer_id':object_id(session.get('customer')),
                'payment_intent':object_id(session.get('payment_intent')),'paid_at':event_time}

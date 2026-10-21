from pathlib import Path
import hmac
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict
import stripe
from .config import Settings
from .store import Store, events, one
from .service import Service, RuleError
from .stripe_gateway import StripeGateway
from .mail import MailSender

class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email: str=Field(max_length=254)
    password: str=Field(max_length=128)
class Activation(BaseModel):
    token: str=Field(min_length=20,max_length=200)
    password: str=Field(min_length=12,max_length=128)
class EmailInput(BaseModel): email: str=Field(max_length=254)
class BookingInput(BaseModel):
    slot_id: str=Field(max_length=64)
    request_id: str=Field(min_length=8,max_length=100)
class SlotInput(BaseModel): starts_at: int
class CloseSlot(BaseModel): slot_id: str=Field(min_length=1,max_length=64)
class LegacyLink(BaseModel):
    email: str=Field(max_length=254)
    password: str=Field(max_length=128)
    username: str=Field(min_length=1,max_length=100)
class LegacyLogin(BaseModel): username: str=Field(min_length=1,max_length=100)

def create_app(settings=None,store=None,gateway=None,sender=None,clock=None):
    settings=settings or Settings.from_env()
    service=Service(store or Store(settings.database_url),settings,**({'clock':clock} if clock else {}))
    gateway=gateway or StripeGateway(settings)
    sender=sender or MailSender(settings)
    app=FastAPI(title='May Bloom member services',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.service=service
    static=Path(__file__).with_name('static')

    @app.exception_handler(RuleError)
    async def rule_error(_,exc): return JSONResponse({'error':exc.message},status_code=exc.status)
    @app.exception_handler(ValueError)
    async def value_error(_,exc): return JSONResponse({'error':'资料无法确认，请重试。 Please check your details.'},status_code=400)

    @app.middleware('http')
    async def secure(request,call_next):
        if request.method not in {'GET','HEAD','OPTIONS'} and request.url.path.startswith('/api/'):
            # Browser requests are same-origin; Streamlit uses separate key-protected routes.
            expected=urlparse(settings.public_url)
            if request.headers.get('origin')!=f'{expected.scheme}://{expected.netloc}':
                return JSONResponse({'error':'Request origin rejected.'},status_code=403)
        if request.headers.get('content-length','0').isdigit() and int(request.headers.get('content-length','0'))>1048576:
            return JSONResponse({'error':'Request too large.'},status_code=413)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def key(request,name,value):
        if not hmac.compare_digest(request.headers.get(name,''),value): raise HTTPException(401,'Unauthorized')
    def admin(request): key(request,'authorization','Bearer '+settings.admin_key)
    def bridge(request): key(request,'x-mb-bridge',settings.bridge_key)
    def session(request): return request.cookies.get('mb_session','')
    def auth_response(token):
        response=JSONResponse({'ok':True})
        response.set_cookie('mb_session',token,httponly=True,secure=settings.production,samesite='strict',max_age=86400,path='/')
        return response

    @app.get('/healthz')
    def health(): return {'ok':True,'live':settings.live,'booking_enabled':settings.booking_enabled}
    @app.get('/')
    def portal(): return FileResponse(static/'index.html')
    app.mount('/static',StaticFiles(directory=static),name='static')

    @app.post('/api/request-activation')
    def activation_request(body:EmailInput):
        service.request_activation(body.email)
        return {'ok':True,'message':'如有符合条件的账号，开通邮件将发送至该邮箱。 If eligible, an activation email will be sent.'}
    @app.post('/api/activate')
    def activate(body:Activation): return auth_response(service.activate(body.token,body.password))
    @app.post('/api/login')
    def login(body:Credentials): return auth_response(service.login(body.email,body.password))
    @app.post('/api/logout')
    def logout(request:Request):
        service.logout(session(request)); response=JSONResponse({'ok':True}); response.delete_cookie('mb_session',path='/'); return response
    @app.get('/api/me')
    def me(request:Request): return service.me(session(request))
    @app.get('/api/slots')
    def available(request:Request): return {'slots':service.available_slots(session(request))}
    @app.post('/api/book')
    def book(body:BookingInput,request:Request):
        return {'ok':True,'booking_id':service.book(session(request),body.slot_id,body.request_id)}

    @app.post('/bridge/login')
    def bridge_login(body:Credentials,request:Request):
        bridge(request); token=service.login(body.email,body.password)
        return {'token':token,**service.tracker_session(token)}
    @app.get('/bridge/me')
    def bridge_me(request:Request):
        bridge(request); token=request.headers.get('authorization','').removeprefix('Bearer ')
        return service.me(token)
    @app.get('/bridge/roster')
    def roster(request:Request):
        bridge(request)
        members=[a for a in service.admin_summary()['accounts'] if a['verified']]
        return {'usernames':[a['username'] for a in members],
                'labels':{a['username']:a['email'] for a in members}}
    @app.post('/bridge/link-legacy')
    def link_legacy(body:LegacyLink,request:Request):
        bridge(request)
        token=service.login(body.email,body.password)
        service.link_legacy(token,body.username)
        return {'token':token,**service.me(token)}
    @app.post('/bridge/legacy-login')
    def legacy_login(body:LegacyLogin,request:Request):
        bridge(request)
        return service.legacy_login(body.username)

    @app.post('/stripe/webhook')
    async def webhook(request:Request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>1048576: raise HTTPException(413,'Request too large')
        try: event=stripe.Webhook.construct_event(bytes(raw),request.headers.get('stripe-signature',''),settings.webhook_secret).to_dict()
        except (ValueError,stripe.SignatureVerificationError): raise HTTPException(400,'Invalid webhook signature')
        if event.get('livemode') is not settings.live: raise HTTPException(400,'Stripe environment mismatch')
        return await run_in_threadpool(reconcile,event)

    def reconcile(event):
        kind=event['type']; eid=event['id']; obj=event['data']['object']; at=event['created']
        with service.store.read() as c:
            if one(c,events,events.c.id==eid): return {'received':True,'result':'duplicate'}
        try:
            if kind in {'checkout.session.completed','checkout.session.async_payment_succeeded'}:
                result=service.fulfill(eid,kind,gateway.checkout(obj['id'],at))
            elif kind=='invoice.paid': result=service.fulfill(eid,kind,gateway.invoice(obj['id'],at))
            elif kind in {'customer.subscription.updated','customer.subscription.deleted'}:
                result=service.reconcile_subscription(eid,kind,gateway.subscription(obj['id'],at))
            else:
                if kind in {'charge.refunded','charge.dispute.created','invoice.payment_failed','checkout.session.async_payment_failed'}:
                    service.flag(eid,kind)
                result=service.fulfill(eid,kind,None)
        except Exception:
            # Non-2xx lets Stripe retry. Never return provider payloads or secrets to callers.
            raise HTTPException(503,'Payment reconciliation could not be confirmed; retry later.')
        return {'received':True,'result':result}

    @app.get('/admin/summary')
    def summary(request:Request): admin(request); return service.admin_summary()
    @app.post('/admin/slots')
    def publish_slot(body:SlotInput,request:Request): admin(request); return {'slot_id':service.publish_slot(body.starts_at)}
    @app.post('/admin/close-slot')
    def close_slot(body:CloseSlot,request:Request): admin(request); service.close_slot(body.slot_id); return {'ok':True}
    @app.post('/admin/run-jobs')
    def jobs(request:Request):
        admin(request)
        if not settings.smtp_host and isinstance(sender,MailSender): raise HTTPException(503,'Email is not configured')
        service.enqueue_reminders()
        return {'sent':service.deliver_pending(sender)}
    @app.get('/api/coach/summary')
    def coach_summary(request:Request): service.coach_authorized(session(request)); return service.admin_summary()
    @app.post('/api/coach/slots')
    def coach_slot(body:SlotInput,request:Request): service.coach_authorized(session(request)); return {'slot_id':service.publish_slot(body.starts_at)}
    @app.post('/api/coach/close-slot')
    def coach_close(body:CloseSlot,request:Request): service.coach_authorized(session(request)); service.close_slot(body.slot_id); return {'ok':True}
    return app

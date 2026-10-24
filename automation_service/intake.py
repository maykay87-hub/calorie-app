"""Private post-payment preparation; encrypted append-only questionnaire versions."""
import json
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from .service import RuleError
from .store import bookings, grants, intakes, one, rows


class IntakeAnswers(BaseModel):
    model_config=ConfigDict(extra='forbid', strict=True)
    preferred_name: str=Field(min_length=1,max_length=100)
    phone: str=Field(default='',max_length=60)
    age: int|None=Field(default=None,ge=0,le=120)
    sex: str=Field(default='',max_length=80)
    height_cm: float|None=Field(default=None,gt=0,le=260,allow_inf_nan=False)
    weight_kg: float|None=Field(default=None,gt=0,le=500,allow_inf_nan=False)
    goals: str=Field(min_length=1,max_length=1500)
    medical_history: str=Field(default='',max_length=3000)
    medicines: str=Field(default='',max_length=2000)
    allergies: str=Field(default='',max_length=1500)
    activity: str=Field(default='',max_length=1500)
    relevant_context: str=Field(default='',max_length=1500)


class IntakeSubmission(BaseModel):
    model_config=ConfigDict(extra='forbid', strict=True)
    booking_id: str=Field(min_length=1,max_length=64)
    request_id: str=Field(min_length=8,max_length=100)
    consent: bool
    answers: IntakeAnswers


class IntakeService:
    def __init__(self,service): self.service=service

    def _enabled(self):
        if not self.service.settings.intake_enabled:
            raise RuleError('会前问卷尚未开放。 Preparation form is not open.',503)

    def _booking(self,c,account,booking_id):
        booking=one(c,bookings,bookings.c.id==booking_id,bookings.c.account_id==account['id'])
        if not booking: raise RuleError('预约不存在。 Booking not found.',404)
        grant=one(c,grants,grants.c.id==booking['grant_id'],grants.c.revoked==False)
        if not grant or grant['plan']=='tracker-monthly':
            raise RuleError('请联系 May 核对咨询。 Consultation review required.',403)
        return booking

    def get(self,token,booking_id):
        self._enabled();s=self.service
        with s.store.read() as c:
            account=s.account_for(c,token);self._booking(c,account,booking_id)
            versions=rows(c,intakes,intakes.c.account_id==account['id'],intakes.c.booking_id==booking_id)
            latest=max(versions,key=lambda row:row['version']) if versions else None
            return {'submitted':bool(latest),'submitted_at':latest['created_at'] if latest else None,
                    'answers':json.loads(s.cipher.decrypt(latest['payload'].encode())) if latest else None}

    def submit(self,token,body):
        self._enabled();s=self.service
        if body.consent is not True:
            raise RuleError('请阅读并确认资料使用说明。 Please review and confirm the privacy notice.')
        answers=body.answers.model_dump()
        if not answers['preferred_name'].strip() or not answers['goals'].strip():
            raise RuleError('请填写称呼和咨询目标。 Please provide your name and consultation goals.')
        with s.store.write() as c:
            account=s.account_for(c,token);self._booking(c,account,body.booking_id)
            previous=one(c,intakes,intakes.c.account_id==account['id'],intakes.c.request_id==body.request_id)
            if previous:
                if (previous['booking_id']!=body.booking_id
                        or json.loads(s.cipher.decrypt(previous['payload'].encode()))!=answers):
                    raise RuleError('请重新提交更新。 Request already used for a different update.',409)
                return {'ok':True,'submitted_at':previous['created_at']}
            iid=uuid4().hex
            version=1+max((row['version'] for row in rows(c,intakes,intakes.c.booking_id==body.booking_id)),default=0)
            c.execute(intakes.insert().values(id=iid,account_id=account['id'],booking_id=body.booking_id,
                request_id=body.request_id,created_at=s.now(),version=version,consent_version=s.settings.intake_consent_version,
                payload=s.cipher.encrypt(json.dumps(answers,ensure_ascii=False).encode()).decode()))
            if s.settings.coach_email:
                s._queue(c,'intake:'+iid,{'to':s.settings.coach_email,'kind':'intake_notice',
                    'subject':'May Bloom · 会前资料已提交 / Preparation submitted',
                    'body':f"顾客已提交会前资料，请登入管理页面查看。\nPreparation details were submitted. Sign in to view them.\n\n{s.settings.public_url}"})
        return {'ok':True,'submitted_at':s.now()}

    def coach_get(self,token,booking_id):
        self._enabled();s=self.service;s.coach_authorized(token)
        with s.store.read() as c:
            versions=rows(c,intakes,intakes.c.booking_id==booking_id)
            return {'versions':[{'submitted_at':row['created_at'],'version':row['version'],
                'answers':json.loads(s.cipher.decrypt(row['payload'].encode())),
                'consent_version':row['consent_version']}
                for row in sorted(versions,key=lambda row:row['version'],reverse=True)]}

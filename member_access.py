"""Optional server-to-server membership bridge. Disabled unless configured."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

class MembershipUnavailable(Exception): pass
class MembershipDenied(Exception): pass

def config(secrets):
    options=dict(secrets.get('membership_service',{}))
    if options.get('enabled') is not True: return None
    url=options.get('url','').rstrip('/')
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path):
        raise MembershipUnavailable('Membership service URL must be an HTTPS origin.')
    if len(options.get('bridge_key',''))<32: raise MembershipUnavailable('Membership bridge is not configured.')
    return {'url':url,'bridge_key':options['bridge_key']}

def _request(options,path,body=None,token=None,opener=urlopen):
    headers={'Content-Type':'application/json','X-MB-Bridge':options['bridge_key']}
    if token: headers['Authorization']='Bearer '+token
    req=Request(options['url']+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with opener(req,timeout=6) as response: result=json.load(response)
    except HTTPError as exc:
        if exc.code in {401,403}: raise MembershipDenied('Sign in or renew access.') from None
        raise MembershipUnavailable('Membership verification unavailable.') from None
    except (URLError,TimeoutError,OSError,ValueError):
        raise MembershipUnavailable('Membership verification unavailable.') from None
    if not isinstance(result,dict): raise MembershipUnavailable('Invalid membership response.')
    return result

def _validate(result):
    if not _username(result.get('username')):
        raise MembershipDenied('Invalid managed account identity.')
    if type(result.get('active')) is not bool: raise MembershipUnavailable('Invalid membership response.')
    if not result['active']: raise MembershipDenied('Membership access is not active.')
    if not isinstance(result.get('ends_at'),int) or result['ends_at'] <= 0:
        raise MembershipUnavailable('Invalid membership period.')
    return result

def _username(value):
    return (isinstance(value,str) and 1<=len(value)<=100 and value.strip()==value
            and value.isprintable() and value.casefold()!='admin')

def login(options,email,password,opener=urlopen):
    result=_validate(_request(options,'/bridge/login',{'email':email,'password':password},opener=opener))
    if not isinstance(result.get('token'),str) or len(result['token'])<32: raise MembershipUnavailable('Invalid session.')
    return result

def verify(options,token,username,opener=urlopen):
    result=_validate(_request(options,'/bridge/me',token=token,opener=opener))
    if result['username']!=username: raise MembershipDenied('Account mismatch.')
    return result

def roster(options,opener=urlopen):
    result=_request(options,'/bridge/roster',opener=opener)
    values=result.get('usernames',[])
    if not isinstance(values,list) or any(not _username(u) for u in values):
        raise MembershipUnavailable('Invalid managed student list.')
    return values

def link_legacy(options,email,password,username,opener=urlopen):
    result=_validate(_request(options,'/bridge/link-legacy',{'email':email,'password':password,'username':username},opener=opener))
    if result['username']!=username or not isinstance(result.get('token'),str) or len(result['token'])<32:
        raise MembershipUnavailable('Could not confirm account link.')
    return result

def legacy_login(options,username,opener=urlopen):
    result=_request(options,'/bridge/legacy-login',{'username':username},opener=opener)
    if result.get('managed') is False: return None
    _validate(result)
    if result['username']!=username or not isinstance(result.get('token'),str) or len(result['token'])<32:
        raise MembershipUnavailable('Could not confirm legacy access.')
    return result

def roster_with_labels(options,opener=urlopen):
    result=_request(options,'/bridge/roster',opener=opener)
    values=result.get('usernames',[]); labels=result.get('labels',{})
    if not isinstance(values,list) or any(not _username(u) for u in values) or not isinstance(labels,dict):
        raise MembershipUnavailable('Invalid managed student list.')
    return values,{u:label for u,label in labels.items() if u in values and isinstance(label,str) and len(label)<=254}

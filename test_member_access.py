import io
import json
import unittest
from urllib.error import HTTPError, URLError
from member_access import (config,login,verify,roster,legacy_login,MembershipDenied,MembershipUnavailable)

class MemberAccessTests(unittest.TestCase):
    def options(self): return {'url':'https://members.example.invalid','bridge_key':'b'*40}
    def opener(self,result): return lambda *a,**k:io.BytesIO(json.dumps(result).encode())
    def test_disabled_configuration_never_needs_service(self):
        self.assertIsNone(config({}))
        self.assertIsNone(config({'membership_service':{'enabled':False}}))
        with self.assertRaises(MembershipUnavailable): config({'membership_service':{'enabled':True,'url':'http://unsafe','bridge_key':'x'}})
    def test_managed_session_and_identity_cannot_be_swapped(self):
        result={'username':'mb_'+'a'*32,'active':True,'ends_at':9999999999,'token':'t'*43}
        self.assertEqual(login(self.options(),'student@example.invalid','password',self.opener(result))['token'],'t'*43)
        with self.assertRaises(MembershipDenied): verify(self.options(),'t'*43,'another',self.opener(result))
        result['username']='admin'
        with self.assertRaises(MembershipDenied): login(self.options(),'x','x',self.opener(result))
    def test_outage_and_inactive_access_never_become_authenticated(self):
        def offline(*a,**k): raise URLError('offline')
        with self.assertRaises(MembershipUnavailable): login(self.options(),'x','x',offline)
        with self.assertRaises(MembershipDenied): login(self.options(),'x','x',self.opener({'username':'student','active':False}))
    def test_existing_legacy_account_is_supported_without_impersonating_admin(self):
        self.assertIsNone(legacy_login(self.options(),'old',self.opener({'managed':False})))
        self.assertEqual(roster(self.options(),self.opener({'usernames':['old-student','mb_'+'a'*32]}))[0],'old-student')
        with self.assertRaises(MembershipUnavailable): roster(self.options(),self.opener({'usernames':['admin']}))

if __name__=='__main__': unittest.main()

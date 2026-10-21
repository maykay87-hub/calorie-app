"""Real Streamlit flows; synthetic in-memory Sheets and a mocked private bridge."""
import unittest
from unittest.mock import patch
import pytest
import test_app_flow as legacy_flow
from member_access import MembershipUnavailable, MembershipDenied

@pytest.fixture
def tracker():
    case=legacy_flow.AppFlowTests('test_login_form_rejects_wrong_password_then_clears_successful_credentials')
    case.setUp()
    case.at.secrets['membership_service']={'enabled':True,'legacy_link_enabled':True,'url':'https://members.example.invalid','bridge_key':'b'*40}
    yield case
    case.doCleanups()

def managed(username='mb_'+'c'*32):
    return {'username':username,'display_name':'Preview member','token':'t'*43,'active':True,'ends_at':4102444800}

def test_new_member_can_sign_in_save_and_reopen_own_records(tracker):
    at=tracker.at
    at.session_state['logged_in']=False
    with patch('member_access.login',return_value=managed()):
        at.run()
        at.text_input(key='login_user').set_value('preview@example.invalid')
        at.text_input(key='login_pass').set_value('Example-password-123!')
        at.button(key='login_btn').click().run()
    assert not at.exception
    assert at.session_state['username']==managed()['username']
    assert 'Preview Member' in next(h.value for h in at.header if 'Preview' in h.value)
    next(b for b in at.button if b.label.startswith('Add Meal')).click().run()
    at.button(key='save_bottom_food').click().run()
    assert not at.exception
    assert dict(zip(tracker.sheet.rows[0],tracker.sheet.rows[-1]))['username']==managed()['username']
    assert at.session_state['food_log']
    at.session_state['daily_drafts']={}
    at.run()
    assert len(at.session_state['food_log'])==1

def test_member_verification_outage_preserves_draft_and_does_not_fall_back_to_legacy(tracker):
    at=tracker.at
    at.session_state['membership_token']='t'*43
    at.session_state['membership_checked']=0
    at.session_state['membership_ends_at']=4102444800
    at.session_state['unsaved_marker']='keep this draft'
    with patch('member_access.verify',side_effect=MembershipUnavailable('offline')):
        at.run()
    assert not at.exception and at.session_state['unsaved_marker']=='keep this draft'
    assert any('Access could not be confirmed' in x.value for x in at.warning)
    assert not any(b.label.startswith('Add Meal') for b in at.button)

def test_existing_account_links_without_replacing_saved_username(tracker):
    at=tracker.at
    with patch('member_access.link_legacy',return_value=managed('student')):
        at.run()
        at.text_input(key='member_email').set_value('preview@example.invalid')
        at.text_input(key='member_password').set_value('Example-password-123!')
        next(b for b in at.button if b.label.startswith('关联当前账号')).click().run()
    assert not at.exception
    assert at.session_state['username']=='student' and at.session_state['membership_token']=='t'*43
    next(b for b in at.button if b.label.startswith('Add Meal')).click().run()
    at.button(key='save_bottom_food').click().run()
    assert dict(zip(tracker.sheet.rows[0],tracker.sheet.rows[-1]))['username']=='student'

def test_coach_sees_new_member_by_email_and_can_publish_feedback(tracker):
    at=tracker.at
    at.secrets['passwords']={'student':'test-pass','admin':'coach-pass'}
    at.session_state['username']='admin'
    username=managed()['username']
    with patch('member_access.roster_with_labels',return_value=([username],{username:'preview@example.invalid'})):
        at.run()
        assert not at.exception
        assert 'preview@example.invalid' in at.selectbox(key='coach_student').options
        at.selectbox(key='coach_student').select('preview@example.invalid').run()
        at.text_area(key='review_body_'+username).set_value('A synthetic review for this member.')
        next(b for b in at.button if b.label.startswith('发布给这位')).click().run()
    assert not at.exception
    assert tracker.feedback.rows[-1][0]==username

def test_linked_expired_member_cannot_bypass_access_using_old_password(tracker):
    at=tracker.at;at.session_state['logged_in']=False
    with patch('member_access.legacy_login',side_effect=MembershipDenied('expired')):
        at.run()
        at.text_input(key='login_user').set_value('student')
        at.text_input(key='login_pass').set_value('test-pass')
        at.button(key='login_btn').click().run()
    assert not at.exception and not at.session_state['logged_in']

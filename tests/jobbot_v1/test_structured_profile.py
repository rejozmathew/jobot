"""Structured facts reuse real meanings; fixtures never touch candidate data."""
import copy
import json
from pathlib import Path

import pytest

from job_applier.application_answers import approved_answer
from job_applier.managed import Service
from job_applier.managed_shared import ProtocolError


def candidate(tmp_path, **sections):
    service = Service.create(tmp_path / 'profile.db', instance_id='profile-test')
    service.identity(identity_id='candidate', person_key='person', email='candidate@example.test',
                     profile={'identity': {'email': 'candidate@example.test'}, **sections})
    return service


def learned(service, question, answer, **kwargs):
    return service.save_library_answer(identity_id='candidate', question=question, answer=answer, **kwargs)


def test_background_and_drug_consent_are_independent_and_false_is_an_answer():
    profile = {'standard_answers': {'background_check_consent': True, 'drug_test_consent': False}}
    assert approved_answer('Are you willing to submit to a background check?*', profile) is True
    assert approved_answer('Do you agree to a background check if hired?', profile) is True
    assert approved_answer('Are you willing to submit to a drug test?', profile) is False
    assert approved_answer('Are you willing to submit to a background check and drug test?', profile) is False
    assert approved_answer('Are you unwilling to submit to a background check?', profile) is None
    assert approved_answer('Do you consent to a credit check and fingerprinting?', profile) is None
    assert approved_answer('Are you willing to submit to a background check?', {}) is None


def test_criminal_and_employer_question_meanings_are_not_collapsed():
    profile = {'standard_answers': {'felony_conviction': False, 'arrest_history': True,
                                   'government_employment_history': False}}
    assert approved_answer('Have you ever been convicted of a felony?', profile) is False
    assert approved_answer('Have you ever been arrested?', profile) is True
    assert approved_answer('Have you ever been convicted of a misdemeanor?', profile) is None
    assert approved_answer('Have you been convicted of a felony in the last seven years, excluding sealed records?', profile) is None
    assert approved_answer('Are you currently, planning to be, or have you previously been employed by a government or regulatory entity?', profile) is False
    assert approved_answer('Were you referred to Example Corp by a government official?', profile) is None


def test_legacy_work_authorization_is_visible_until_explicit_us_answer_is_saved():
    from job_applier.profile_questions import value_for_field
    path = 'standard_answers.authorized_to_work_us'
    question = 'Are you legally authorized to work in the United States?'
    profile = {'standard_answers': {'legally_authorized_to_work': True}}
    assert value_for_field(profile, path) is True
    assert approved_answer(question, profile) is True
    profile['standard_answers']['authorized_to_work_us'] = False
    assert approved_answer(question, profile) is False
    profile['standard_answers']['authorized_to_work_us'] = None
    assert approved_answer(question, profile) is None


def test_templates_offer_unknown_values_and_keep_compatibility_copy():
    root = Path(__file__).resolve().parents[2]
    template = json.loads((root / 'profile.json.template').read_text())
    assert template == json.loads((root / 'profile.example.json').read_text())
    for name in ('criminal_conviction_history', 'arrest_history', 'currently_employed',
                 'outside_employment', 'sms_consent', 'professional_license_disciplinary_history'):
        assert template['standard_answers'][name] is None
    assert template['work_authorization']['i140_approved'] is None
    assert template['work_preferences']['open_to_individual_contributor'] is None


def test_suggestions_keep_scope_and_conflicting_answers_visible(tmp_path):
    service = candidate(tmp_path, work_authorization={'country': 'United States'})
    yes = learned(service, 'Do you want to receive SMS text messages?', 'Yes')
    no = learned(service, 'Do I want to receive SMS text messages?', 'No', conditions={'country':'us'})
    learned(service, 'Are you currently employed?', 'No', scope='company', scope_key='Example')
    learned(service, 'Are you open to an individual contributor role?', 'Yes', conditions={'country': 'canada'})
    editor = service.profile_editor(identity_id='candidate')
    proposals = editor['suggestions']
    assert {r['entry_id'] for r in proposals} == {yes['id'], no['id']}
    assert all(r['status'] == 'conflict' for r in proposals)
    assert 'standard_answers.sms_consent' in {r['field'] for r in proposals}


def test_save_promotes_only_selected_global_fact_preserves_sources_and_other_answers(tmp_path):
    service = candidate(tmp_path, summary='Keep this', standard_answers={'background_check_consent': False})
    source = learned(service, 'Do I want to receive SMS text messages?', 'No, I do not want SMS text messages.')
    company = learned(service, 'Do you consent to interview recording?', 'Yes', scope='company', scope_key='Example')
    before = service.candidate('candidate')
    profile = copy.deepcopy(before['profile'])
    profile['standard_answers']['sms_consent'] = False
    result = service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=before['profile_hash'],
                                  promotions=[{'field': 'standard_answers.sms_consent', 'entry_id': source['id'], 'revision': 1}])
    current = service.candidate('candidate')['profile']
    assert current['summary'] == 'Keep this'
    assert current['standard_answers']['background_check_consent'] is False
    assert current['standard_answers']['sms_consent'] is False
    assert current['profile_answer_sources']['standard_answers.sms_consent']['entry_id'] == source['id']
    assert result['file_sync']['status'] == 'not_configured'
    assert next(e for e in service.answer_library()['entries'] if e['id'] == company['id'])['scope'] == 'company'
    with pytest.raises(ProtocolError, match='profile_revision_conflict'):
        service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=before['profile_hash'])


def test_scoped_answer_cannot_be_promoted_as_candidate_wide_fact(tmp_path):
    service = candidate(tmp_path)
    source = learned(service, 'Do you consent to interview recording?', 'Yes', scope='company', scope_key='Example')
    current = service.candidate('candidate')
    profile = dict(current['profile'], standard_answers={'interview_recording_consent': True})
    with pytest.raises(ProtocolError, match='profile_source_changed'):
        service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=current['profile_hash'],
                             promotions=[{'field': 'standard_answers.interview_recording_consent', 'entry_id': source['id'], 'revision': 1}])
    assert service.candidate('candidate')['profile_hash'] == current['profile_hash']


def test_profile_export_preserves_credentials_policy_and_other_candidates(tmp_path):
    service = candidate(tmp_path)
    target = tmp_path / 'private-profile.json'
    private = {'identity': {'email': 'candidate@example.test'}, 'accounts': {'default': {'password': 'synthetic-only'}},
               'application_answer_policy': {'routine_privacy_consent': True}, 'resume': {'text': 'Legacy text'},
               'portal_password_overrides': {'fixture': {'password': 'synthetic-other'}}}
    target.write_text(json.dumps(private))
    service.executor_config = {'identity_id': 'candidate', 'profile_export_path': str(target)}
    old = service.candidate('candidate')
    profile = dict(old['profile'], standard_answers={'background_check_consent': False})
    result = service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    saved = json.loads(target.read_text())
    assert result['file_sync']['status'] == 'synced'
    assert saved['standard_answers']['background_check_consent'] is False
    for k in ('accounts', 'application_answer_policy', 'portal_password_overrides'):
        assert saved[k] == private[k]
    assert saved['resume']['text'] == 'Legacy text'
    service.identity(identity_id='other', person_key='other', email='other@example.test', profile={})
    other = service.candidate('other')
    result = service.save_profile(identity_id='other', profile={'standard_answers': {'background_check_consent': True}}, expected_profile_hash=other['profile_hash'])
    assert result['file_sync']['status'] == 'not_configured'
    assert json.loads(target.read_text()) == saved


def test_export_failure_keeps_database_save_and_can_be_retried(tmp_path):
    service = candidate(tmp_path)
    target = tmp_path / 'missing' / 'profile.json'
    service.executor_config = {'identity_id': 'candidate', 'profile_export_path': str(target)}
    old = service.candidate('candidate')
    profile = dict(old['profile'], standard_answers={'sms_consent': False})
    result = service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    assert result['file_sync']['status'] == 'error'
    assert service.candidate('candidate')['profile']['standard_answers']['sms_consent'] is False
    target.parent.mkdir()
    result = service.sync_profile_file(identity_id='candidate')
    assert result['status'] == 'synced'
    assert json.loads(target.read_text())['standard_answers']['sms_consent'] is False


def test_scoped_exceptions_and_human_answers_survive_profile_edits(tmp_path):
    from test_answer_queue import connected, request
    service, session, owner, _, _ = connected(tmp_path)
    wording = 'Are you willing to submit to a background check?'
    question = request(service, owner, question=wording)
    learned(service, wording, 'Yes')
    old = service.candidate('candidate')
    before_snapshot = service.attempt(owner['attempt_id'])['profile_json']
    profile = dict(old['profile'], standard_answers={'background_check_consent': False})
    service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    current = service.questions_for_attempt(owner['attempt_id'])['questions'][0]
    assert current['answer']['label'] == 'No' and current['answer_source'] == 'approved_profile'
    assert service.attempt(owner['attempt_id'])['profile_json'] == before_snapshot
    learned(service, 'Do you agree to a background check if hired?', 'Yes', scope='job', scope_key=session['job_id'])
    current = service.questions_for_attempt(owner['attempt_id'])['questions'][0]
    assert current['answer']['label'] == 'Yes' and current['answer_source'] == 'answer_library'
    service.answer_questions(answers=[{'question_id':question['id'], 'answer':'No', 'expected_revision':current['revision']}])
    old = service.candidate('candidate')
    profile['standard_answers']['background_check_consent'] = True
    service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    current = service.questions_for_attempt(owner['attempt_id'])['questions'][0]
    assert current['answer']['label'] == 'No' and current['answer_source'] == 'user_dashboard'


def test_saved_helper_answers_share_structured_profile_and_scoped_precedence():
    from job_applier.application_answers import saved_answer, saved_answer_basis
    from test_answer_queue import QUESTION
    question = dict(QUESTION, question='Are you willing to submit to a background check?')
    entry = dict(id='scoped', identity_id='candidate', question='Do you agree to a background check if hired?',
                 answer='Yes', aliases=[], scope='company', scope_key='example', conditions={}, state='active', revision=1)
    package = dict(job={'id':'job', 'company':'Example'}, attempt={'profile_json':{'standard_answers':{'background_check_consent':False}}},
                   answer_library=[], saved_questions=[])
    assert saved_answer(question, package) == {'value':'no', 'label':'No'}
    assert saved_answer_basis(question, package) == 'profile:standard_answers.background_check_consent'
    package['answer_library'] = [entry]
    assert saved_answer(question, package) == {'value':'yes', 'label':'Yes'}
    assert saved_answer_basis(question, package) == 'answer_library:scoped:1'


def test_latest_human_response_can_supply_a_fact_without_promoting_model_conflicts(tmp_path):
    from test_answer_queue import connected, request
    service, _, owner, _, _ = connected(tmp_path)
    old = service.candidate('candidate')
    service.save_profile(identity_id='candidate', profile=dict(old['profile'], work_authorization={'country':'United States'}),
                         expected_profile_hash=old['profile_hash'])
    question = request(service, owner, question='Has an I-140 petition been approved on your behalf?')
    service.answer_questions(answers=[{'question_id':question['id'], 'answer':'Yes', 'expected_revision':0}])
    proposal = next(s for s in service.profile_editor(identity_id='candidate')['suggestions'] if s.get('question_id') == question['id'])
    assert proposal['field'] == 'work_authorization.i140_approved' and proposal['value'] is True
    old = service.candidate('candidate')
    profile = copy.deepcopy(old['profile']);profile['work_authorization']['i140_approved'] = True
    service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'],
                         promotions=[{'field':proposal['field'], 'question_id':question['id'], 'revision':proposal['revision']}])
    assert service.candidate('candidate')['profile']['profile_answer_sources'][proposal['field']]['question_id'] == question['id']


def test_boolean_types_cannot_silently_become_numbers_and_secrets_stay_out(tmp_path):
    service = candidate(tmp_path, standard_answers={'background_check_consent': True})
    old = service.candidate('candidate')
    with pytest.raises(ProtocolError, match='invalid_profile_answer'):
        service.save_profile(identity_id='candidate', profile=dict(old['profile'], standard_answers={'background_check_consent': 1}),
                             expected_profile_hash=old['profile_hash'])
    with pytest.raises(ValueError):
        service.save_profile(identity_id='candidate', profile=dict(old['profile'], accounts={'password':'synthetic-secret'}),
                             expected_profile_hash=old['profile_hash'])
    assert service.candidate('candidate')['profile_hash'] == old['profile_hash']


def test_profile_operations_are_operator_only_and_export_paths_are_not_exposed(tmp_path):
    from fastapi.testclient import TestClient
    from job_applier.managed_api import create_app
    service = candidate(tmp_path)
    service.executor_config = {'identity_id':'candidate', 'profile_export_path':str(tmp_path/'profile.json')}
    operator, worker = 'o'*32, 'w'*32
    client = TestClient(create_app(service, operator_token=operator, worker_tokens={worker:'worker'}), base_url='http://127.0.0.1')
    headers = {'Authorization':'Bearer '+operator, 'X-JobBot-Instance':service.instance_id}
    response = client.post('/v1/profile_editor', json={'identity_id':'candidate'}, headers=headers)
    assert response.status_code == 200 and response.json()['sections']
    assert str(tmp_path) not in response.text
    headers['Authorization'] = 'Bearer '+worker
    for operation in ('profile_editor', 'save_profile', 'sync_profile_file'):
        assert client.post('/v1/'+operation, json={'identity_id':'candidate'}, headers=headers).status_code == 403


def test_private_file_drift_is_visible_and_password_lock_protects_shared_writes(tmp_path):
    from job_applier.workspace_process import FileLock
    service = candidate(tmp_path, standard_answers={'sms_consent':False})
    target = tmp_path/'profile.json'
    service.executor_config = {'identity_id':'candidate', 'profile_export_path':str(target)}
    assert service.sync_profile_file(identity_id='candidate')['status'] == 'synced'
    raw = json.loads(target.read_text());raw['standard_answers']['sms_consent'] = True
    target.write_text(json.dumps(raw))
    assert service.profile_file_status(identity_id='candidate')['status'] == 'out_of_date'
    with FileLock(str(target)+'.password-overrides.lock'):
        result = service.sync_profile_file(identity_id='candidate')
        assert result == {'status':'error', 'code':'local_lock_busy'}
        assert json.loads(target.read_text()) == raw
    assert service.sync_profile_file(identity_id='candidate')['status'] == 'synced'
    assert json.loads(target.read_text())['standard_answers']['sms_consent'] is False


def test_alias_edits_update_one_fact_and_conflicting_edits_preserve_existing_data(tmp_path):
    service = candidate(tmp_path, standard_answers={'requires_sponsorship':True}, work_authorization={'needs_sponsorship':True, 'status':'Example'})
    old = service.candidate('candidate')
    profile = copy.deepcopy(old['profile']);profile['work_authorization']['needs_sponsorship'] = False
    service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    current = service.candidate('candidate')
    assert current['profile']['standard_answers']['requires_sponsorship'] is False
    assert current['profile']['work_authorization']['status'] == 'Example'
    profile = copy.deepcopy(current['profile']);profile['standard_answers']['requires_sponsorship'] = True
    profile['work_authorization']['needs_sponsorship'] = None
    with pytest.raises(ProtocolError, match='invalid_profile_answer'):
        service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=current['profile_hash'])
    assert service.candidate('candidate')['profile_hash'] == current['profile_hash']


def test_source_changes_after_preview_are_not_silently_promoted(tmp_path):
    service = candidate(tmp_path)
    entry = learned(service, 'Do you want to receive SMS text messages?', 'No')
    old = service.candidate('candidate')
    learned(service, entry['question'], 'Yes', entry_id=entry['id'], expected_revision=1)
    with pytest.raises(ProtocolError, match='profile_source_changed'):
        service.save_profile(identity_id='candidate', profile=dict(old['profile'], standard_answers={'sms_consent':False}),
                             expected_profile_hash=old['profile_hash'], promotions=[{'field':'standard_answers.sms_consent', 'entry_id':entry['id'], 'revision':1}])
    assert service.candidate('candidate')['profile_hash'] == old['profile_hash']


def test_clearing_a_promoted_answer_does_not_restore_its_old_general_library_value(tmp_path):
    from job_applier.managed_answer_library import resolve_with_profile
    service = candidate(tmp_path, standard_answers={'sms_consent':False})
    entry = learned(service, 'Do you want to receive SMS text messages?', 'No')
    old = service.candidate('candidate')
    profile = copy.deepcopy(old['profile']);profile['standard_answers']['sms_consent'] = None
    service.save_profile(identity_id='candidate', profile=profile, expected_profile_hash=old['profile_hash'])
    profile = service.candidate('candidate')['profile']
    result = resolve_with_profile({'question':entry['question'], 'kind':'text'}, {}, [entry], profile)
    assert result['answer'] is None and result['source'] == 'approved_profile'

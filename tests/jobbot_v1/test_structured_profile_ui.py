"""Exercise profile editing through the shipped UI using synthetic fixtures."""
import json

from job_applier.profile_questions import schema
from test_dispatch_queue_ui import dashboard_check


def profile_check(check):
    fixture = r'''
v.candidates=[{id:'candidate',email:'candidate@example.test'}];
const editor={candidate:{id:'candidate',person_key:'person',email:'candidate@example.test',profile_hash:'revision-1',profile:{identity:{email:'candidate@example.test',full_name:'Example Candidate'},standard_answers:{background_check_consent:false},summary:'Keep this advanced fact'}},
 sections:SECTIONS,suggestions:[{field:'standard_answers.sms_consent',label:'Do you want SMS?',value:false,current:null,question:'Do I want to receive SMS text messages?',entry_id:'entry',revision:3,source_type:'answer_library',status:'new',saved_at:'2026-01-01T00:00:00Z'}],file_sync:{status:'synced'}};
let calls=[];
w.fetch=async(path,options)=>{const payload=JSON.parse(options.body||'{}');calls.push([path,payload]);return {ok:true,status:200,json:async()=>path.endsWith('profile_editor')?JSON.parse(JSON.stringify(editor)):{candidate:{id:'candidate',profile_hash:'revision-2'},file_sync:{status:'synced'}}};};
w.draw(v);w.noRefresh();
await w.drawProfile(v);
'''.replace('SECTIONS', json.dumps(schema()))
    dashboard_check(fixture + check)


def test_unset_and_no_stay_distinct_and_structured_edits_preserve_json_and_revision():
    profile_check(r'''
const background=doc.querySelector('[data-profile-field="standard_answers.background_check_consent"]');
const sms=doc.querySelector('[data-profile-field="standard_answers.sms_consent"]');
assert(background.value==='false'&&sms.value==='','No collapsed into unset');
sms.value='false';sms.dispatchEvent(new w.Event('input',{bubbles:true}));
let profile=JSON.parse(doc.getElementById('profile-json').value);
assert(profile.standard_answers.sms_consent===false&&profile.summary==='Keep this advanced fact','Editing lost advanced facts');
editor.candidate.profile_hash='changed-elsewhere';await w.drawProfile(v);
assert(sms.value==='false','Polling erased draft');
await doc.getElementById('profile-form').onsubmit({preventDefault(){}});
const save=calls.find(c=>c[0].endsWith('/save_profile'))[1];
assert(save.expected_profile_hash==='revision-1','Polling replaced draft revision');
assert(save.profile.standard_answers.sms_consent===false,'False answer not saved');
assert(doc.getElementById('notice').textContent.includes('private profile JSON'),'File save result missing');
''')


def test_unchanged_poll_preserves_focus_and_open_suggestions_but_reload_discards_draft():
    profile_check(r'''
const suggestions=doc.querySelector('#profile-suggestions details');suggestions.open=true;
const input=doc.querySelector('[data-profile-field="standard_answers.background_check_consent"]');input.focus();
await w.drawProfile(v);
assert(doc.querySelector('#profile-suggestions details')===suggestions&&suggestions.open,'Polling collapsed suggestions');
assert(doc.activeElement===input,'Polling replaced the focused control');
input.value='true';input.dispatchEvent(new w.Event('input',{bubbles:true}));
await doc.getElementById('profile-reload').onclick();
assert(doc.querySelector('[data-profile-field="standard_answers.background_check_consent"]').value==='false','Reload kept discarded draft');
''')


def test_saved_answer_suggestion_carries_exact_source_revision_and_raw_json_stays_editable():
    profile_check(r'''
doc.querySelector('#profile-suggestions button').click();
assert(doc.querySelector('[data-profile-field="standard_answers.sms_consent"]').value==='false','Suggestion not reflected in controls');
let raw=JSON.parse(doc.getElementById('profile-json').value);raw.summary='Updated advanced fact';
doc.getElementById('profile-json').value=JSON.stringify(raw);doc.getElementById('profile-json').dispatchEvent(new w.Event('change',{bubbles:true}));
await doc.getElementById('profile-form').onsubmit({preventDefault(){}});
const save=calls.find(c=>c[0].endsWith('/save_profile'))[1];
assert(save.promotions.length===1&&save.promotions[0].entry_id==='entry'&&save.promotions[0].revision===3,'Source revision lost');
assert(save.profile.summary==='Updated advanced fact','Raw JSON editing was overwritten');
''')


def test_new_edits_during_save_remain_unsaved_and_export_failure_is_visible():
    profile_check(r'''
let release;w.fetch=async()=>({ok:true,status:200,json:()=>new Promise(r=>release=r)});
const sms=doc.querySelector('[data-profile-field="standard_answers.sms_consent"]');sms.value='false';sms.dispatchEvent(new w.Event('input',{bubbles:true}));
const saving=doc.getElementById('profile-form').onsubmit({preventDefault(){}});
await new Promise(r=>setTimeout(r,0));
sms.value='true';sms.dispatchEvent(new w.Event('input',{bubbles:true}));
release({candidate:{id:'candidate',profile_hash:'revision-2'},file_sync:{status:'error'}});await saving;
assert(JSON.parse(doc.getElementById('profile-json').value).standard_answers.sms_consent===true,'Late save erased new draft');
assert(doc.getElementById('notice').textContent.includes('still unsaved'),'New draft status missing');
assert(doc.getElementById('profile-file-sync').textContent.includes('could not be synced'),'Export failure hidden');
assert(doc.querySelector('#profile-file-sync button'),'No export retry control');
''')


def test_legacy_authorization_is_shown_and_can_be_cleared_without_erasing_general_value():
    profile_check(r'''
editor.candidate.profile.standard_answers.legally_authorized_to_work=true;
await w.drawProfile(v);
const field=doc.querySelector('[data-profile-field="standard_answers.authorized_to_work_us"]');
assert(field.value==='true','Legacy authorization hidden');
field.value='';field.dispatchEvent(new w.Event('input',{bubbles:true}));
await doc.getElementById('profile-form').onsubmit({preventDefault(){}});
const save=calls.find(c=>c[0].endsWith('/save_profile'))[1];
assert(save.profile.standard_answers.authorized_to_work_us===null,'Explicit unset lost');
assert(save.profile.standard_answers.legally_authorized_to_work===true,'Unrelated general authorization overwritten');
''')

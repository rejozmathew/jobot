"""Dashboard queue feedback uses synthetic records and the shipped JavaScript."""
import json
import subprocess

import pytest

from test_workday_dom import JSDOM, ROOT


def dashboard_check(check):
    if not JSDOM.exists():
        pytest.skip('optional jsdom fixture dependency not installed')
    harness = r'''
const fs=require('fs'),{JSDOM}=require(process.argv[1]),d=JSON.parse(fs.readFileSync(0,'utf8'));
const w=new JSDOM(d.html,{url:'http://localhost/',runScripts:'outside-only'}).window;
w.setInterval=callback=>{w.pollRefresh=callback;return 0;};w.fetch=()=>new Promise(()=>{});
w.eval(d.script+'\nwindow.draw=v=>{state.view=v;renderQueue(v)};window.drawAnswers=v=>{state.view=v;renderAnswers(v)};window.drawAccounts=v=>{state.view=v;renderAccounts(v)};window.disconnect=showLogin;window.drawSettings=renderSettings;window.drawProfile=renderProfile;window.drawModelSelection=c=>{state.modelCatalog=c;renderModelSelection()};window.noRefresh=()=>{refresh=async()=>{}};window.startRefresh=()=>{state.instance="fixture";state.modelCatalog={providers:[]};return refresh()};window.refreshAPI=handler=>{window.fetch=async path=>({ok:true,status:200,json:()=>handler(path.slice(4))})};');
const doc=w.document;
const v={jobs:[],candidates:[],assets:[],answer_queue:{groups:[]},
 dispatch_queue:{installed:true,worker_online:true,enabled:true,counts:{},items:[]},
 local_runtime:{workspaces:[{}],sessions:[]}};
function assert(ok,reason){if(!ok)throw Error(reason);}
(async()=>{CHECK})().then(()=>w.close()).catch(e=>{console.error(e);w.close();process.exitCode=1;});
'''.replace('CHECK', check)
    result = subprocess.run(['node', '-e', harness, str(JSDOM)], input=json.dumps({
        'html': (ROOT/'job_applier/static/jobbot.html').read_text(encoding='utf-8'),
        'script': (ROOT/'job_applier/static/jobbot.js').read_text(encoding='utf-8')}),
        capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


def test_saved_jobs_and_interrupted_requests_are_not_waiting_to_run():
    dashboard_check(r'''
v.jobs=[{id:'saved',company:'Saved Role',status:'queued'},
 {id:'held',company:'Review Role',status:'queued',eligibility:'held'},
 {id:'retry',company:'Interrupted Role',status:'queued'}];
v.dispatch_queue.items=[{job_id:'retry',state:'finished',outcome:'interrupted',detail:'Executor stopped'}];
w.draw(v);
let rows=[...doc.querySelectorAll('#queue-rows tr')];
assert(rows[0].cells[2].textContent.includes('Awaiting automatic pickup'),'Saved intake lacks automatic pickup state');
assert(rows[1].cells[2].textContent.includes('Awaiting automatic pickup'),'New intake still requires manual queueing');
assert(rows[2].cells[2].textContent.includes('Interrupted'),'Interrupted request hidden');
assert(rows[2].cells[2].textContent.includes('schedules recovery'),'Interrupted request has no retry guidance');
assert(doc.getElementById('dispatcher-status').textContent.includes('automatically'),'Automatic pickup missing');
v.dispatch_queue.items.unshift({job_id:'retry',state:'queued'});
v.dispatch_queue.counts={queued:1,finished:1};w.draw(v);
rows=[...doc.querySelectorAll('#queue-rows tr')];
assert(rows[2].cells[2].querySelector('.badge').textContent==='Queued','Fresh retry still shows interrupted');
v.dispatch_queue.items[0].state='dispatched';v.dispatch_queue.counts={dispatched:1};w.draw(v);
assert(doc.querySelectorAll('#queue-rows tr')[2].cells[2].querySelector('.badge').textContent==='In progress','Live dispatch hidden');
v.dispatch_queue.latest_by_job={saved:{state:'queued'},retry:{state:'finished',outcome:'interrupted'}};
w.draw(v);
assert(doc.querySelectorAll('#queue-rows tr')[0].cells[2].querySelector('.badge').textContent==='Queued','Queue entry outside recent history hidden');
assert(doc.querySelectorAll('#queue-rows tr')[2].cells[2].querySelector('.badge').textContent==='Interrupted','Latest request ignored in favor of history');
''')


def test_queue_explains_startup_wait_without_claiming_application_progress():
    dashboard_check(r'''
v.dispatch_queue.detail='waiting_for_executor_startup';
v.dispatch_queue.ready_count=2;v.dispatch_queue.active_count=0;w.draw(v);
assert(doc.getElementById('dispatcher-status').textContent.includes('Waiting for Hermes'),'Missing executor startup wait');
assert(doc.getElementById('dispatcher-status').textContent.includes('stay queued'),'Startup must retain requests');
v.dispatch_queue.detail='waiting_for_browser_startup';w.draw(v);
assert(doc.getElementById('dispatcher-status').textContent.includes('Waiting for the application browser'),'Missing browser startup wait');
v.dispatch_queue.automation_paused=true;w.draw(v);
assert(!doc.getElementById('dispatcher-status').textContent.includes('Waiting for the application browser'),'Pause must supersede stale startup status');
''')


def test_run_next_feedback_uses_fresh_server_counts_without_blocking_request():
    dashboard_check(r'''
w.draw(v);w.noRefresh();
let calls=[];
let response={installed:true,worker_online:true,counts:{}};
w.fetch=async(path,options)=>{calls.push([path,JSON.parse(options.body)]);return {ok:true,status:200,json:async()=>response};};
// Stale UI claims queued work; the actual command response says empty.
v.dispatch_queue.counts={queued:2};w.draw(v);
await doc.getElementById('queue-run-next').onclick();
assert(calls.length===1&&calls[0][1].command==='run_next','UI blocked or changed the existing wake request');
assert(doc.getElementById('notice').textContent.includes('No eligible jobs'),'Empty queue falsely promises a launch');
assert(doc.getElementById('notice').textContent.includes('automatically'),'Missing automatic pickup guidance');
response={worker_online:false,counts:{queued:1}};
await doc.getElementById('queue-run-next').onclick();
assert(doc.getElementById('notice').textContent.includes('offline'),'Offline worker falsely promises a launch');
response={worker_online:true,counts:{dispatched:1}};
await doc.getElementById('queue-run-next').onclick();
assert(doc.getElementById('notice').textContent.includes('already in progress'),'Active request falsely treated as pending work');
response={worker_online:true,counts:{queued:1,dispatched:1}};
await doc.getElementById('queue-run-next').onclick();
assert(doc.getElementById('notice').textContent.includes('current application'),'Busy worker lacks waiting explanation');
response={worker_online:true,counts:{queued:1}};
await doc.getElementById('queue-run-next').onclick();
assert(doc.getElementById('notice').textContent.includes('Request saved'),'Queued request not acknowledged');
''')


def test_discovery_controls_save_numeric_settings_and_show_runner_and_schedule():
    dashboard_check(r'''
v.discovery={installed:true,batch_size:5,interval_hours:4,runner:'JobBot discovery service / Hermes',
 scheduler_recent:true,next_due_at:'2026-09-15T20:00:00Z',last_run:{started_at:'2026-09-15T16:00:00Z',state:'completed'}};
w.draw(v);w.noRefresh();
w.drawSettings({version:7,values:{discovery_batch_size:5,discovery_interval_hours:4}});
const area=doc.getElementById('discovery-setting-fields');
assert(area.querySelectorAll('input').length===2,'Discovery settings hidden among operational fields');
assert(doc.getElementById('discovery-status').textContent.includes('5 jobs every 4 hours'),'Schedule not visible');
assert(doc.getElementById('discovery-status').textContent.includes('Hermes'),'Runner not visible');
assert(doc.getElementById('discovery-status').textContent.includes('Next due'),'Next run not visible');
area.querySelector('[data-setting=discovery_interval_hours]').value=3;
let payload;
w.fetch=async(path,options)=>{payload=JSON.parse(options.body);return {ok:true,status:200,json:async()=>({})};};
await doc.getElementById('settings-form').onsubmit({preventDefault(){}});
assert(payload.changes.discovery_interval_hours===3&&payload.changes.discovery_batch_size===5,'Discovery settings did not save as numbers');
assert(payload.expected_version===7,'Versioned settings save bypassed');
v.discovery.scheduler_recent=false;v.discovery.last_run.state='running';w.draw(v);
assert(doc.getElementById('discovery-status').textContent.includes('Last scheduler check'),'Manual discovery must not imply an active scheduler');
''')


def test_delayed_retry_time_attempt_count_and_next_application_check_are_visible():
    dashboard_check(r'''
v.jobs=[{id:'retry',company:'Retry Fixture',status:'queued'}];
v.dispatch_queue.counts={queued:1};v.dispatch_queue.ready_count=0;v.dispatch_queue.scheduled_count=1;
v.dispatch_queue.next_automatic_at='2026-09-16T10:01:00Z';v.dispatch_queue.next_job_at='2026-09-16T14:00:00Z';
v.dispatch_queue.items=[{job_id:'retry',state:'queued',attempt_number:2,waiting_for_retry:true,next_attempt_at:'2026-09-16T14:00:00Z'}];
w.draw(v);w.noRefresh();
const cell=doc.querySelector('#queue-rows tr').cells[2];
assert(cell.textContent.includes('Retry scheduled')&&cell.textContent.includes('Attempt 2 of 3')&&cell.textContent.includes('Retry at'),'Retry timing hidden');
assert(doc.getElementById('application-schedule').textContent.includes('Next application check'),'Application check time hidden');
w.fetch=async()=>({ok:true,status:200,json:async()=>v.dispatch_queue});
await doc.getElementById('queue-run-next').onclick();
assert(doc.getElementById('notice').textContent.includes('scheduled for later'),'Run next falsely promises immediate retry');
v.dispatch_queue.items=[{job_id:'retry',state:'finished',outcome:'failed',attempt_number:3,automatic_limit_reached:true,detail:'Employer unavailable'}];
w.draw(v);
assert(doc.querySelector('#queue-rows tr').cells[2].textContent.includes('Needs attention'),'Exhausted retries hidden');
assert(doc.querySelector('#queue-rows tr').cells[2].textContent.includes('Employer unavailable'),'Failure reason hidden');
v.jobs=[{id:'held-skip',company:'Skipped Fixture',status:'queued',eligibility:'held',metadata_json:'{"verdict":"Skip"}'}];
w.draw(v);
assert(doc.querySelector('#queue-rows tr').cells[2].textContent.includes('Not selected for application'),'Skipped posting falsely promises automatic pickup');
''')


def test_country_and_actual_posting_date_are_visible_without_guessing_update_date():
    dashboard_check(r'''
v.jobs=[{id:'dated',company:'Dated Fixture',status:'queued',metadata_json:'{"country":"US","posted_at":"2026-09-10","location":"Remote"}'},
 {id:'undated',company:'Undated Fixture',status:'queued',metadata_json:'{"location":"Remote (United States)","updated_at":"2026-09-15"}'}];
w.draw(v);
const rows=doc.querySelectorAll('#queue-rows tr');
assert(rows[0].cells[4].textContent==='United States','Country code not readable');
assert(rows[0].cells[5].textContent.includes('2026-09-10'),'Posting date hidden or shifted');
assert(rows[1].cells[4].textContent==='United States','Explicit country in stored location not displayed');
assert(rows[1].cells[5].textContent==='Unavailable','Update date fabricated as posting date');
''')


def test_refresh_during_inflight_request_waits_for_fresh_view():
    dashboard_check(r'''
v.health={instance_id:'fixture',db_path:'fixture.db'};
v.settings={version:1,values:{mode:'development',submission_mode:'review'}};
v.runs=[];v.accounts=[];v.resources=[];
let release;let calls=0;
w.refreshAPI(async command=>{
 assert(command==='view','Unexpected request');
 calls++;
 if(calls===1)return await new Promise(resolve=>{release=()=>resolve({...v,marker:'stale'});});
 return {...v,marker:'fresh'};
});
const first=w.startRefresh();
let completed=false;
const afterMutation=w.startRefresh().then(()=>{completed=true;});
await Promise.resolve();await Promise.resolve();
assert(!completed,'Refresh returned before an in-flight request finished');
release();
await Promise.all([first,afterMutation]);
assert(calls===2,'Mutation must fetch a new view after the earlier request');
let recoveredCalls=0;
w.refreshAPI(async()=>{recoveredCalls++;return v;});
await w.startRefresh();
assert(recoveredCalls===1,'Completed refresh left future requests blocked');
''')


def test_passive_poll_does_not_extend_a_slow_explicit_refresh():
    dashboard_check(r'''
v.health={instance_id:'fixture',db_path:'fixture.db'};
v.settings={version:1,values:{mode:'development',submission_mode:'review'}};
v.runs=[];v.accounts=[];v.resources=[];
let calls=0;
w.refreshAPI(async()=>{
 calls++;
 if(calls===1)w.pollRefresh();
 return v;
});
await w.startRefresh();
assert(calls===1,'Passive poll unnecessarily extended an active refresh');
await w.startRefresh();
assert(calls===2,'Explicit refresh after completion did not fetch');
''')

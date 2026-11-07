"""Native synthetic receipt after a locale-only Dayforce document transition."""
import asyncio
import json
import os
import pytest

from job_applier.application_runtime import browser_action
from test_popup_document_handoff import popup_fixture


@pytest.mark.parametrize('portal,suffix,attribution', [
    ('CANDIDATEPORTAL', '', False),
    ('CANDIDATEPORTAL', '/apply/manualApplication', False),
    ('candidateportal', '', False),
    ('candidateportal', '/apply/manualApplication', False),
    ('candidateportal', '/apply/manualApplication?applicationSource=Manual', True),
])
def test_locale_transition_recovers_same_session_and_submits(tmp_path, suffix, portal, attribution):
    if not os.environ.get('JOBBOT_BROWSER_TEST_EXE'):
        pytest.skip('Explicit isolated browser executable required')
    async def run():
        path='/en-US/synthetic/'+portal+'/jobs/123'+suffix
        async with popup_fixture(tmp_path, hosts=('jobs.dayforcehcm.com','forms.example.test'),
                                 posting_path=path,tls=True,deadline_minutes=60) as (page,s,session,own,client,cfg,entry,final,receipts):
            before=s.attempt(own['attempt_id'])
            deadline=json.loads(s.session(session['id'])['metadata_json']).get('application_deadline')
            assert deadline['limit_seconds'] == 3600
            current = entry.rsplit('/apply/', 1)[0] + path.replace('/en-US/', '/')
            if attribution:
                original_gate = await asyncio.to_thread(s.browser_observe, **own,
                    target_id=page.target_id, cdp_url=page.fixture_endpoint)
                assert original_gate['identity']['status'] == 'same_job'
                await page.evaluate("history.pushState({},'',location.href+'&ref=Simplify&src=Simplify&utm_source=Simplify')")
                current += '&ref=Simplify&source=Simplify&utm_source=Simplify'
            else:
                current += '/apply'
            await page.evaluate("history.replaceState({},'',"+json.dumps(current)+");document.body.innerHTML="+json.dumps(
                '<h1>Application review</h1><label>Full name<input id="name" required></label>'
                '<button onclick="if(!event.isTrusted)return;'+
                "fetch('/submitted',{method:'POST'});document.body.innerHTML='<h1>Thank you for applying</h1>'"+
                '">Submit application</button>'))
            gate=await asyncio.to_thread(s.browser_observe,**own,target_id=page.target_id,cdp_url=page.fixture_endpoint)
            assert gate['identity']['status']=='same_job',gate
            assert gate['native_takeover_authorized'],gate
            package=s.application_context(own['attempt_id'])
            filled=await asyncio.to_thread(browser_action,cfg,client,own,package,page.target_id,
                {'method':'fill','selector':'#name','value':'Synthetic Candidate'})
            assert filled['committed']
            submitted=await asyncio.to_thread(browser_action,cfg,client,own,package,page.target_id,
                {'method':'submit','selector':'button'})
            assert submitted['status']=='applied',submitted
            assert receipts==['/submitted']
            assert s.attempt(own['attempt_id'])['started_at']==before['started_at']
            assert s.session(session['id'])['attempt_id']==own['attempt_id']
            assert json.loads(s.session(session['id'])['metadata_json']).get('application_deadline')==deadline
            assert s.job(session['job_id'])['url'].endswith(path)
    asyncio.run(run())

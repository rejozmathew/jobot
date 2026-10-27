"""Synthetic missing-mail recovery; no employer or mailbox interaction."""
import asyncio
import json

import pytest

from job_applier.greenhouse_fast import advance
from job_applier.managed_questions import question_data


def test_missing_email_recovery_does_not_reload_another_ats(monkeypatch):
    from job_applier import application_runtime
    monkeypatch.setattr(application_runtime,'browser_action',lambda *a,**k:pytest.fail('Other ATS was reloaded'))
    class Client:
        def call(self,op,**params):
            if op=='application_context':return {'job':{'url':'https://example.myworkdayjobs.com/job/1'},'attempt':{}}
            assert op=='browser_observe'
            return {'platform':'workday','next_operation':{'operation':'fast_forward','parameters':{'seconds':60}}}
    result=advance({'cdp_url':'unused'},Client(),{'attempt_id':1,'worker_id':'fixture'},
        {'target_id':'owned','recovery':'missing_verification_email'})
    assert result['next_operation']['operation']=='fast_forward'


def test_country_choice_list_is_not_rejected_at_200_options():
    options=[{'value':str(i),'label':'Country '+str(i)} for i in range(249)]
    question=question_data(field='country',question='Country',kind='select',options=options)
    assert question['options']==options


@pytest.mark.parametrize('control',['running','stopped','slice','page_closed'])
def test_unknown_parent_recovery_keeps_unresolved_and_control_handoffs(monkeypatch,control):
    from job_applier import application_runtime,cdp_client,greenhouse_fast
    from job_applier.managed_shared import ProtocolError
    monkeypatch.setattr(application_runtime,'browser_action',lambda *a,**k:pytest.fail('Unresolved document was reloaded'))
    closed=[]
    class Browser:
        async def get_current_page(self):
            if control=='page_closed':raise ProtocolError('owned_page_closed')
            return object()
        async def close(self):closed.append(True)
        @classmethod
        async def connect(cls,*a,**k):return cls()
    class Runner:
        def __init__(self,*a):pass
        async def control(self):
            assert self.deadline is not None
            if control=='stopped':raise ProtocolError('stopped')
            if control=='slice':raise TimeoutError('call_slice_complete')
        async def discover(self):return False
        def report(self,status,reason):return {'status':status,'reason':reason}
    class Client:
        def call(self,op,**params):
            return {} if op=='application_context' else {'platform':'unknown','next_operation':{'operation':'browser'}}
    monkeypatch.setattr(cdp_client,'CDPBrowser',Browser)
    monkeypatch.setattr(greenhouse_fast,'GreenhouseRunner',Runner)
    def call():
        return advance({'cdp_url':'unused'},Client(),{'attempt_id':1,'worker_id':'fixture'},
            {'target_id':'owned','recovery':'missing_verification_email'})
    if control=='page_closed':
        with pytest.raises(ProtocolError,match='owned_page_closed'):call()
        assert closed==[True]
        return
    result=call()
    assert closed==[True]
    assert result['reason']=={'running':'missing_email_recovery_is_greenhouse_only',
        'stopped':'stopped','slice':'call_slice_complete'}[control]
    assert result['status'] in ('continue','inspection_required')


@pytest.mark.parametrize('renewed_verification',[False,True])
@pytest.mark.parametrize('initial_verification',[False,True])
@pytest.mark.parametrize('mode',['top','cross'])
def test_owned_missing_email_recovery_reloads_refills_and_follows_current_submit(tmp_path,monkeypatch,renewed_verification,initial_verification,mode):
    import test_embedded_forms as fixture
    from test_greenhouse_batch import batch_html,batch_profile
    from test_local_sessions import setup,connect,own
    from job_applier.managed_client import LocalClient
    from job_applier import managed_context
    original_platform=managed_context.platform_for_url
    # The isolated fixture uses localhost, never an actual employer hostname.
    monkeypatch.setattr(managed_context,'platform_for_url',
        lambda url:'greenhouse' if mode=='top' and str(url).startswith('http://localhost:') else original_platform(url))
    html=batch_html()
    if renewed_verification:
        html=html.replace("<p>Thank you for applying</p>",
            '<label for="verification">Security code</label><input id="verification" name="security_code" required autocomplete="one-time-code">')
    monkeypatch.setattr(fixture,'FORM_HTML',html)
    async def run():
        async with fixture.fixture_browser(tmp_path,mode=mode) as (page,fixture_package,submissions):
            service,asset,_,ws,cfg=setup(tmp_path/'ledger')
            ws[0].update(cdp_url=page.fixture_endpoint,mode='headless');service.configure_workspaces(ws)
            profile=batch_profile();profile['identity']['email']='candidate@example.test'
            service.identity(identity_id='candidate',person_key='same-person',email='candidate@example.test',profile=profile)
            service.configure({'browser_mode':'headless'},expected_version=service.settings_view()['version'])
            job=service.intake(url=fixture_package['job']['url']);service.eligibility(job['id'],'ready',reason='Synthetic')
            session=connect(service,service.reserve_session(request_id='missing-mail',job_id=job['id'],identity_id='candidate',
                driver_id='fixture',workspace_ids=['workspace-0'],concurrency_limit=1,resume_asset_id=asset['id']),page.target_id)
            owner=own(service,session)
            cfg.update(cdp_url=page.fixture_endpoint,browser_mode='headless',spool_dir=str(tmp_path/'spool'))
            client=LocalClient(cfg,service=service)
            original_call=client.call
            def call(op,**params):
                if op=='application_context':
                    package=original_call(op,**params)
                    package['attempt']['settings_json']=dict(json.loads(package['attempt']['settings_json']),submission_mode='submit')
                    return package
                if op=='submission_intent':params['fixture']=True
                return original_call(op,**params)
            monkeypatch.setattr(client,'call',call)
            if initial_verification:
                document=page
                if mode=='cross':
                    from job_applier.browser_frames import router_for
                    router=await router_for(page,service.application_context(owner['attempt_id']))
                    await router.discover()
                    assert len(router.frames)==1
                    document=next(iter(router.frames.values()))
                await document.evaluate("document.body.innerHTML='<label>Email security code<input name=security_code required autocomplete=one-time-code></label>'")
            before=await page.evaluate('performance.timeOrigin')
            result=await asyncio.to_thread(advance,cfg,client,owner,
                {'target_id':page.target_id,'seconds':30,'recovery':'missing_verification_email'})
            assert result.get('email_recovery_result',{}).get('document_replaced',False) is initial_verification,result
            assert (await page.evaluate('performance.timeOrigin')!=before) is initial_verification
            assert submissions==['/fake-submit']
            if renewed_verification:
                assert result['status']=='application_incomplete',result
                assert result['email_recovery']['operation']=='greenhouse_advance'
                assert 'renewed verification' in result['instruction']
                assert not service.attempt_report(owner['attempt_id'])['attempt']['completed_at']
            else:
                assert result['status']=='applied',result
                assert result['completed_count']==15
            events=service.attempt_report(owner['attempt_id'])['timeline']
            assert any(e['event_type']=='recovery' and e['payload'].get('operation')=='reload' for e in events) is initial_verification
    asyncio.run(run())


def test_embedded_email_recovery_preserves_fixed_capacity_submissions(tmp_path,monkeypatch):
    """Five fixed arrivals, four slots; the executor retains the manual fallback."""
    import threading
    import test_embedded_forms as fixture
    from test_greenhouse_batch import batch_html,batch_profile
    from test_local_sessions import setup,connect,own
    from job_applier import application_deadline,application_runtime,managed_context
    from job_applier.browser_frames import router_for
    from job_applier.cdp_client import CDPBrowser
    from job_applier.managed_client import LocalClient
    from job_applier.workspace_host import browser_command
    monkeypatch.setattr(fixture,'FORM_HTML',batch_html())
    platform=managed_context.platform_for_url
    monkeypatch.setattr(managed_context,'platform_for_url',
        lambda url:'greenhouse' if '/top?' in str(url) else platform(url))
    entered,release=threading.Event(),threading.Event()
    original_browser=application_runtime.browser_action
    recovery_target=None
    def browser(*args,**kwargs):
        if args[4]==recovery_target and args[5].get('method')=='snapshot':
            entered.set()
            assert release.wait(120),'Synthetic control submissions did not complete'
        return original_browser(*args,**kwargs)
    monkeypatch.setattr(application_runtime,'browser_action',browser)
    async def run():
        nonlocal recovery_target
        async with fixture.fixture_browser(tmp_path,'cross') as (initial,packet,submissions):
            service,asset,_,workspaces,cfg=setup(tmp_path/'ledger')
            endpoint=initial.fixture_endpoint
            workspaces[0].update(cdp_url=endpoint,mode='headless',connection_mode='existing');service.configure_workspaces(workspaces)
            profile=batch_profile();profile['identity']['email']='candidate@example.test'
            service.identity(identity_id='candidate',person_key='same-person',email='candidate@example.test',profile=profile)
            service.configure({'browser_mode':'headless','application_concurrency':4},expected_version=service.settings_view()['version'])
            frozen=application_deadline.freeze({},service.settings_view()['values'],service.now())['application_deadline']
            cfg.update(cdp_url=endpoint,browser_mode='headless',spool_dir=str(tmp_path/'spool'))
            base=packet['job']['url'].split('/jobs?',1)[0]
            urls=[packet['job']['url']]+[base+'/top?gh_jid='+str(20000+i) for i in range(1,5)]
            jobs=[];cases=[];connections=[];fallbacks=[];task=None
            for url in urls:
                job=service.intake(url=url);service.eligibility(job['id'],'ready',reason='Synthetic fixed arrivals');jobs.append(job)
            def reserve(i):
                return service.reserve_session(request_id='email-capacity-'+str(i),job_id=jobs[i]['id'],identity_id='candidate',
                    driver_id='fixture-'+str(i),workspace_ids=['workspace-0'],concurrency_limit=4,resume_asset_id=asset['id'],
                    metadata={'application_deadline':frozen})
            async def attach(i,reservation):
                if i==0:page=initial
                else:
                    created=await browser_command(endpoint,'Target.createTarget',{'url':urls[i],'newWindow':True})
                    conn=await CDPBrowser.connect(endpoint,target_id=created['targetId'],expected_mode='headless')
                    connections.append(conn);page=await conn.get_current_page()
                    await page.goto(urls[i])
                session=connect(service,reservation,page.target_id);owner=own(service,session)
                client=LocalClient(cfg,authority=(session['id'],session['driver_id'],'host-workspace-0'))
                original=client.call
                def call(op,**params):
                    if op=='application_context':
                        package=original(op,**params)
                        package['attempt']['settings_json']=dict(json.loads(package['attempt']['settings_json']),submission_mode='submit')
                        return package
                    if op=='submission_intent':params['fixture']=True
                    return original(op,**params)
                monkeypatch.setattr(client,'call',call)
                case={'page':page,'session':session,'owner':owner,'client':client};cases.append(case);return case
            async def advance_case(case,**params):
                return await asyncio.to_thread(advance,cfg,case['client'],case['owner'],{'target_id':case['page'].target_id,'seconds':60,**params})
            async def recover(case):
                result=await advance_case(case,recovery='missing_verification_email')
                if result.get('reason')=='missing_email_recovery_is_greenhouse_only':
                    fallbacks.append(result['reason'])
                    # Baseline executor capability, as exercised in production:
                    # a helper miss continues via shared reload in the same session.
                    entered.set();assert await asyncio.to_thread(release.wait,120)
                    package=case['client'].call('application_context',attempt_id=case['owner']['attempt_id'])
                    await asyncio.to_thread(original_browser,cfg,case['client'],case['owner'],package,recovery_target,
                        {'method':'reload','recovery_reason':'missing_verification_email'})
                    result=await advance_case(case)
                return result
            try:
                for i in range(4):await attach(i,reserve(i))
                assert reserve(4)['state']=='capacity_wait'
                first=cases[0];recovery_target=first['page'].target_id
                router=await router_for(first['page'],service.application_context(first['owner']['attempt_id']));await router.discover()
                await next(iter(router.frames.values())).evaluate("document.body.innerHTML='<label>Security code<input name=security_code autocomplete=one-time-code required></label>'")
                task=asyncio.create_task(recover(first))
                for _ in range(1500):
                    if entered.is_set() or task.done():break
                    await asyncio.sleep(.02)
                if task.done():
                    result=await task
                    assert entered.is_set(),result
                assert entered.is_set(),'Recovery did not reach its resumable boundary'
                results=await asyncio.gather(*(advance_case(case) for case in cases[1:]))
                assert all(r.get('status')=='applied' for r in results),results
                closed=cases[1]
                await browser_command(endpoint,'Target.closeTarget',{'targetId':closed['page'].target_id})
                service.session_stopped(closed['session']['id'],reason='Synthetic submitted tab closed',tabs_closed=True)
                fifth=await attach(4,reserve(4));result=await advance_case(fifth)
                assert result.get('status')=='applied',result
                assert not task.done(),'Recovery must remain resumable while other slots submit'
                release.set();result=await task
                assert result.get('status')=='applied',result
                assert submissions==['/fake-submit']*5
                assert all(service.attempt(c['owner']['attempt_id'])['outcome']=='applied' for c in cases)
                assert all(json.loads(service.session(c['session']['id'])['metadata_json'])['application_deadline']==frozen for c in cases)
                print('fixed-capacity replay: five native submissions, four slots, unchanged frozen deadlines')
                print('manual recovery fallback count:',len(fallbacks))
            finally:
                release.set()
                if task:await asyncio.gather(task,return_exceptions=True)
                for conn in connections:await conn.close()
    asyncio.run(run())

"""Synthetic browser submissions remain independent during authentication recovery."""
import asyncio
import base64
import json
import threading
import pytest

from job_applier import application_deadline, cdp_client
from job_applier.application_runtime import browser_action
from job_applier.cdp_client import CDPBrowser
from job_applier.managed_client import LocalClient
from job_applier.workspace_host import browser_command, WorkspaceHost
from test_embedded_forms import fixture_browser
from test_local_sessions import setup, connect, own


@pytest.mark.parametrize('flow', ['auth', 'dayforce_locale', 'dayforce_attribution'])
def test_auth_recovery_preserves_four_slot_submissions_and_next_admission(tmp_path, monkeypatch, flow):
    waiting, release = threading.Event(), threading.Event()
    original_wait = cdp_client.wait_for_apply_target
    auth_target = None
    login = 'https://login.example.test/u/login/password'
    returned = 'https://applications.example.test/jobs/100/application'

    async def delayed_wait(observation, **kwargs):
        # Hold the recovered helper call while real browser submissions proceed.
        # Other calls retain their real timing and all targets share one ledger.
        if observation.current_target_id == auth_target and not release.is_set():
            waiting.set()
            assert await asyncio.to_thread(release.wait, 180), 'Capacity controls did not finish'
        return await original_wait(observation, **kwargs)

    monkeypatch.setattr(cdp_client, 'wait_for_apply_target', delayed_wait)

    def html_for(url):
        if url == 'https://applications.example.test/jobs/100':
            return '''<html><body><label>Email<input type="email" value="candidate@example.test"></label>
              <label>Privacy<select><option selected>Acknowledge</option></select></label>
              <label><input type="checkbox" checked>I accept</label>
              <button type="button" onclick='location.href="''' + login + '''"'>Next</button></body></html>'''
        if url == login:
            return '''<html><body><label>Password<input type="password" id="password"></label>
              <button type="button" onclick='if(password.value==="synthetic-capacity-password")location.href="''' + returned + '''"'>Log In</button></body></html>'''
        return '''<html><body><h1>Application review</h1><button type="button"
          onclick="document.body.innerHTML='<h1>Thank you for applying</h1>'">Submit application</button></body></html>'''

    async def run():
        nonlocal auth_target
        async with fixture_browser(tmp_path, 'top') as (initial, _, __):
            service, asset, _, workspaces, config = setup(tmp_path / 'ledger')
            endpoint = initial.fixture_endpoint
            workspaces[0].update(cdp_url=endpoint, mode='headless', connection_mode='existing')
            service.configure_workspaces(workspaces)
            settings = {'mode': 'pilot', 'submission_mode': 'submit', 'autofill': 'native',
                        'browser_mode': 'headless', 'application_concurrency': 4,
                        'application_time_limit_minutes': 60}
            service.configure(settings, expected_version=service.settings_view()['version'])
            deadline = application_deadline.freeze({}, service.settings_view()['values'], service.now())['application_deadline']
            secret = tmp_path / 'synthetic-credentials.json'
            secret.write_text(json.dumps({'accounts': {'default': {
                'email': 'candidate@example.test', 'password': 'synthetic-capacity-password'}}}))
            config.update(cdp_url=endpoint, browser_mode='headless', credential_profile_path=str(secret),
                          spool_dir=str(tmp_path / 'spool'))
            cases, browsers, pending, subscriptions = [], [], set(), []
            jobs = []
            for index in range(5):
                url = f'https://applications.example.test/jobs/{100+index}'
                if flow.startswith('dayforce_') and index == 0:
                    url = 'https://jobs.dayforcehcm.com/en-US/synthetic/candidateportal/jobs/100'
                    if flow == 'dayforce_attribution':
                        url += '/apply/manualApplication?applicationSource=Manual'
                job = service.intake(url=url)
                service.eligibility(job['id'], 'ready', reason='Synthetic capacity replay')
                jobs.append(job)

            def reserve(index):
                return service.reserve_session(request_id=f'capacity-{index}', job_id=jobs[index]['id'],
                    identity_id='candidate', driver_id=f'fixture-{index}', workspace_ids=['workspace-0'],
                    concurrency_limit=4, resume_asset_id=asset['id'], metadata={'application_deadline': deadline})

            async def attach(index, reservation):
                created = await browser_command(endpoint, 'Target.createTarget', {'url': 'about:blank', 'newWindow': True})
                target = created['targetId']
                browser = await CDPBrowser.connect(endpoint, target_id=target, expected_mode='headless')
                browsers.append(browser)
                page = await browser.get_current_page()
                async def fulfill(event):
                    await page._session.call('Fetch.fulfillRequest', {'requestId': event['requestId'],
                        'responseCode': 200, 'responseHeaders': [{'name': 'Content-Type', 'value': 'text/html'}],
                        'body': base64.b64encode(html_for(event['request']['url']).encode()).decode()})
                def paused(event):
                    task = asyncio.create_task(fulfill(event)); pending.add(task)
                    task.add_done_callback(pending.discard)
                subscriptions.append(page._session.subscribe('Fetch.requestPaused', paused))
                await page._session.call('Fetch.enable', {'patterns': [{'urlPattern': '*'}]})
                await page.goto(jobs[index]['url'])
                session = connect(service, reservation, target)
                client = LocalClient(config, authority=(session['id'], session['driver_id'], 'host-workspace-0'))
                case = {'page': page, 'session': session, 'client': client, 'owner': own(service, session)}
                cases.append(case)
                return case

            async def action(case, method):
                package = case['client'].service.application_context(case['owner']['attempt_id'])
                return await asyncio.to_thread(browser_action, config, case['client'], case['owner'],
                    package, case['page'].target_id, {'method': method, 'selector': 'button'})

            auth_task = None
            try:
                for index in range(4):
                    await attach(index, reserve(index))
                assert reserve(4)['state'] == 'capacity_wait'
                auth_target = cases[0]['page'].target_id
                async def locale_recovery():
                    page = cases[0]['page']
                    destination = 'https://jobs.dayforcehcm.com/synthetic/candidateportal/jobs/100/apply'
                    if flow == 'dayforce_attribution':
                        destination += '/manualApplication?applicationSource=Manual&ref=Simplify&source=Simplify&utm_source=Simplify'
                    await page.evaluate("history.replaceState({},'',"+json.dumps(destination)+");")
                    gate = await asyncio.to_thread(cases[0]['client'].service.browser_observe, **cases[0]['owner'],
                        target_id=page.target_id, cdp_url=endpoint)
                    # Keep this occupied slot while other real submissions run.
                    # The baseline still exercises every control before failure.
                    waiting.set()
                    assert await asyncio.to_thread(release.wait, 180)
                    assert gate['identity']['status'] == 'same_job', gate
                    return await action(cases[0], 'submit')
                auth_task = asyncio.create_task(locale_recovery() if flow.startswith('dayforce_')
                                                else action(cases[0], 'click'))
                # A baseline without this recovery returns instead of reaching the
                # wait; still exercise every successful control before reporting it.
                for _ in range(500):
                    if waiting.is_set() or auth_task.done(): break
                    await asyncio.sleep(.01)
                results = await asyncio.gather(*(action(case, 'submit') for case in cases[1:]))
                assert all(result.get('status') == 'applied' for result in results), results
                closed = await browser_command(endpoint, 'Target.closeTarget', {'targetId': cases[1]['page'].target_id})
                assert closed['success']
                service.session_stopped(cases[1]['session']['id'], reason='Synthetic submitted tab closed', tabs_closed=True)
                fifth = await attach(4, reserve(4))
                result = await action(fifth, 'submit')
                assert result.get('status') == 'applied', result
                for case in cases:
                    metadata = json.loads(service.session(case['session']['id'])['metadata_json'])
                    assert metadata['application_deadline'] == deadline
                assert not release.is_set()
                print('capacity replay: four control submissions, next admission, and original deadlines preserved')
                if auth_task.done():
                    await auth_task  # Surface fixture/navigation errors after exercising controls.
                assert waiting.is_set() and not auth_task.done(), 'Recovery did not retain its call'
                release.set()
                result = await auth_task
                if flow.startswith('dayforce_'):
                    assert result.get('status') == 'applied', result
                    assert all(service.attempt(case['owner']['attempt_id'])['outcome'] == 'applied' for case in cases)
                    print('dayforce capacity replay: five real synthetic confirmations; original deadlines preserved')
                    return
                assert result.get('target_handoff'), result
                auth = cases[0]
                host = object.__new__(WorkspaceHost)
                host.service, host.config = auth['client'].service, config
                host.workspace_id, host.host_id = 'workspace-0', 'host-workspace-0'
                host.workspace = {'cdp_url': endpoint, 'mode': 'headless'}
                result = await asyncio.to_thread(host.dispatch, {'instance_id': service.instance_id,
                    'session_id': auth['session']['id'], 'driver_id': auth['session']['driver_id'],
                    'operation': 'credentials', 'parameters': {'password_ref': '#password'}})
                assert result.get('values_committed'), result
                await action(auth, 'click')
                assert await auth['page'].evaluate('location.href') == returned
                result = await action(auth, 'submit')
                assert result.get('status') == 'applied', result
                assert all(service.attempt(case['owner']['attempt_id'])['outcome'] == 'applied' for case in cases)
            finally:
                release.set()
                if auth_task: await asyncio.gather(auth_task, return_exceptions=True)
                if pending: await asyncio.gather(*pending, return_exceptions=True)
                for unsubscribe in subscriptions: unsubscribe()
                for browser in browsers: await browser.close()

    asyncio.run(run())

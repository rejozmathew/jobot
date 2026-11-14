"""Existing-browser lifecycle: synthetic records, no live applications."""
import json
import os
from pathlib import Path

import pytest

from job_applier import workspace_host as wh
from job_applier.workspace_host import WorkspaceHost
from tests.jobbot_v1.test_local_sessions import setup, reserve, connect, own


def fixture_host(tmp_path):
    service, asset, jobs, workspaces, config = setup(tmp_path)
    workspaces[0]['connection_mode'] = 'existing'
    Path(workspaces[0]['user_data_dir']).mkdir()
    service.configure_workspaces(workspaces)
    session = reserve(service, asset, jobs)
    config.update(spool_dir=str(tmp_path/'spool'), require_simplify=False)
    host = WorkspaceHost(config, session['workspace_id'], 'host-'+session['workspace_id'])
    service.host_registered(host.workspace_id, host.host_id, wh.process_identity(os.getpid()))
    return host, service, session


def test_existing_browser_is_never_launched_or_owned(tmp_path, monkeypatch):
    host, service, session = fixture_host(tmp_path)
    monkeypatch.setattr(wh, 'endpoint_info', lambda _: {'webSocketDebuggerUrl':'ws://127.0.0.1:19600/devtools/browser/existing'})
    monkeypatch.setattr('job_applier.workspace_attachment.existing_profile_process', lambda _: os.getpid())
    monkeypatch.setattr('job_applier.workspace_attachment.verify_connection_process', lambda *args: 'headed')
    monkeypatch.setattr(wh.OwnedProcess, 'launch', lambda *a, **k: pytest.fail('Launched an owned browser'))
    # A supported existing-browser attachment must not reject an occupied endpoint.
    host.start_browser()
    assert host.browser is None


def test_stop_closes_only_durable_application_tab_and_popups(tmp_path, monkeypatch):
    host, service, session = fixture_host(tmp_path)
    session = connect(service, session, 'application')
    with service.tx() as db:
        meta=json.loads(session['metadata_json'])
        meta['browser_attachment']={'browser_id':'ws://browser/one','target_ids':['application']}
        db.execute('UPDATE application_sessions SET metadata_json=? WHERE id=?',(json.dumps(meta),session['id']))
    tabs=[{'targetId':'dashboard','type':'page'}, {'targetId':'mail','type':'page'},
          {'targetId':'application','type':'page'}, {'targetId':'popup','type':'page','openerId':'application'}]
    calls=[]
    monkeypatch.setattr(wh, 'endpoint_info', lambda _: {'webSocketDebuggerUrl':'ws://browser/one'})
    async def command(endpoint, method, params=None):
        calls.append((method,params))
        if method=='Target.getTargets': return {'targetInfos':list(tabs)}
        assert method=='Target.closeTarget', method
        tabs[:]=[t for t in tabs if t['targetId']!=params['targetId']]
        return {'success':True}
    monkeypatch.setattr(wh,'browser_command',command)
    host.stop_session(session,'Missing verification code')
    assert {t['targetId'] for t in tabs}=={'dashboard','mail'}
    assert service.session(session['id'])['ended_at']
    assert service.attempt(session['attempt_id'])['outcome']=='interrupted'


def test_failed_tab_closure_keeps_cleanup_pending(tmp_path, monkeypatch):
    host, service, session = fixture_host(tmp_path)
    session = connect(service, session, 'application')
    with service.tx() as db:
        meta=json.loads(session['metadata_json'])
        meta['browser_attachment']={'browser_id':'ws://browser/one','target_ids':['application']}
        db.execute('UPDATE application_sessions SET metadata_json=? WHERE id=?',(json.dumps(meta),session['id']))
    monkeypatch.setattr(wh,'endpoint_info',lambda _: {'webSocketDebuggerUrl':'ws://browser/one'})
    async def command(endpoint,method,params=None):
        if method=='Target.getTargets':return {'targetInfos':[{'targetId':'dashboard','type':'page'},{'targetId':'application','type':'page'}]}
        return {'success':False}
    monkeypatch.setattr(wh,'browser_command',command)
    with pytest.raises(Exception,match='tab_close_unconfirmed'):
        host.stop_session(session,'Stopped')
    assert not service.session(session['id'])['ended_at']


def test_stale_preparation_does_not_replace_connected_application(tmp_path, monkeypatch):
    host, service, pending = fixture_host(tmp_path)
    connected = connect(service, pending, 'original')
    launches = []
    monkeypatch.setattr(host, 'start_browser', lambda: launches.append('launch'))
    async def prepare_target(session):return 'duplicate', {'synthetic': True}
    monkeypatch.setattr(host, 'prepare_target', prepare_target)
    monkeypatch.setattr(host, 'stop_session', lambda *a, **kw: launches.append('stop'))
    # The monitor captured preparing while another thread completed readiness.
    host.prepare(pending)
    assert launches == []
    assert service.session(pending['id']) == connected


@pytest.mark.parametrize('outcome', ['failed', 'blocked', 'applied'])
def test_terminal_cleanup_retains_all_targets_after_attachment_refresh(tmp_path, monkeypatch, outcome):
    host, service, session = fixture_host(tmp_path)
    session = connect(service, session, 'original')
    service.session_browser_attachment(session['id'], host.host_id,
        {'browser_id': 'ws://existing', 'target_ids': ['original']})
    service.session_browser_attachment(session['id'], host.host_id,
        {'browser_id': 'ws://existing', 'target_ids': ['replacement']}, 'replacement')
    tabs = [{'type': 'page', 'targetId': target} for target in ('original', 'replacement', 'personal', 'peer')]
    tabs.append({'type': 'page', 'targetId': 'popup', 'openerId': 'original'})
    monkeypatch.setattr(wh, 'endpoint_info', lambda _: {'webSocketDebuggerUrl': 'ws://existing'})
    async def command(endpoint, method, params=None):
        if method == 'Target.getTargets':return {'targetInfos': list(tabs)}
        assert method == 'Target.closeTarget'
        tabs[:] = [t for t in tabs if t['targetId'] != params['targetId']]
        return {'success': True}
    monkeypatch.setattr(wh, 'browser_command', command)
    if outcome == 'applied':service.submission_intent(**own(service, session), evidence='Synthetic submission', fixture=True)
    service.finish(**own(service, session), outcome=outcome, evidence='Synthetic terminal outcome', quiescent=True)
    host.supervise_session(service.session(session['id']))
    assert {t['targetId'] for t in tabs} == {'personal', 'peer'}
    assert service.session(session['id'])['ended_at']
    assert service.attempt(session['attempt_id'])['outcome'] == outcome


def test_attachment_target_history_does_not_cross_browser_incarnations(tmp_path):
    host, service, session = fixture_host(tmp_path)
    service.session_browser_attachment(session['id'], host.host_id,
        {'browser_id': 'ws://old', 'target_ids': ['old-target']}, 'old-target')
    service.session_browser_attachment(session['id'], host.host_id,
        {'browser_id': 'ws://new', 'target_ids': ['new-target']}, 'new-target')
    attachment = json.loads(service.session(session['id'])['metadata_json'])['browser_attachment']
    assert attachment['target_ids'] == ['new-target']


@pytest.mark.parametrize('outcome',['blocked','failed','applied'])
def test_session_accepts_tab_quiescence_without_claiming_browser_killed(tmp_path,outcome):
    host, service, session = fixture_host(tmp_path)
    session=connect(service,session)
    if outcome=='applied':service.submission_intent(**own(service,session),evidence='Synthetic local submission',fixture=True)
    service.finish(**own(service,session),outcome=outcome,evidence='Synthetic outcome',quiescent=True)
    result=service.session_stopped(session['id'],reason='Application tab closed',tabs_closed=True)
    assert result['state']=='finished'
    assert service.attempt(session['attempt_id'])['outcome']==outcome


def test_manual_launcher_does_not_set_automation_switches(tmp_path):
    from job_applier.workspace_attachment import launch_arguments
    host, _, _ = fixture_host(tmp_path)
    args=launch_arguments(host.workspace,['http://127.0.0.1:8000','https://mail.google.com/'])
    assert '--remote-debugging-port=19600' in args
    assert not any(a.startswith(('--enable-automation','--headless','--disable-blink-features')) for a in args)
    assert args[-2:]==['http://127.0.0.1:8000','https://mail.google.com/']


def test_browser_replacement_does_not_close_new_personal_tabs(tmp_path,monkeypatch):
    host,service,session=fixture_host(tmp_path)
    session=connect(service,session,'application')
    service.session_browser_attachment(session['id'],host.host_id,{'browser_id':'ws://old','target_ids':['application']})
    monkeypatch.setattr(wh,'endpoint_info',lambda _: {'webSocketDebuggerUrl':'ws://replacement'})
    async def command(*args,**kwargs):pytest.fail('Touched a replacement browser')
    monkeypatch.setattr(wh,'browser_command',command)
    host.stop_session(session,'Previous browser closed')
    assert service.session(session['id'])['ended_at']


def test_cleanup_recovers_target_creation_crash_marker(tmp_path,monkeypatch):
    host,service,session=fixture_host(tmp_path)
    service.session_browser_attachment(session['id'],host.host_id,
        {'browser_id':'ws://existing','marker':'about:blank#jobbot-unique','target_ids':[]})
    tabs=[{'targetId':'personal','type':'page','url':'about:blank'},
          {'targetId':'created-before-crash','type':'page','url':'about:blank#jobbot-unique'}]
    monkeypatch.setattr(wh,'endpoint_info',lambda _: {'webSocketDebuggerUrl':'ws://existing'})
    async def command(endpoint,method,params=None):
        if method=='Target.getTargets':return {'targetInfos':list(tabs)}
        assert method=='Target.closeTarget'
        tabs[:]=[t for t in tabs if t['targetId']!=params['targetId']]
        return {'success':True}
    monkeypatch.setattr(wh,'browser_command',command)
    host.stop_session(session,'Startup interrupted')
    assert [t['targetId'] for t in tabs]==['personal']
    assert service.session(session['id'])['ended_at']


def test_last_application_tab_does_not_exit_shared_browser(tmp_path,monkeypatch):
    host,service,session=fixture_host(tmp_path)
    session=connect(service,session,'application')
    service.session_browser_attachment(session['id'],host.host_id,{'browser_id':'ws://existing','target_ids':['application']})
    tabs=[{'targetId':'application','type':'page'}]
    monkeypatch.setattr(wh,'endpoint_info',lambda _: {'webSocketDebuggerUrl':'ws://existing'})
    async def command(endpoint,method,params=None):
        if method=='Target.getTargets':return {'targetInfos':list(tabs)}
        if method=='Target.createTarget':
            assert params=={'url':'about:blank'}
            tabs.append({'targetId':'neutral','type':'page'})
            return {'targetId':'neutral'}
        assert method=='Target.closeTarget' and len(tabs)>1
        tabs[:]=[t for t in tabs if t['targetId']!=params['targetId']]
        return {'success':True}
    monkeypatch.setattr(wh,'browser_command',command)
    host.stop_session(session,'Finished')
    assert [t['targetId'] for t in tabs]==['neutral']


def test_linux_process_title_and_default_profile_lock(tmp_path,monkeypatch):
    from job_applier import workspace_attachment as attachment
    args=attachment.linux_arguments(b'/opt/brave/brave --remote-debugging-port=19600 --no-first-run\0\0')
    assert args==['/opt/brave/brave','--remote-debugging-port=19600','--no-first-run']
    host,_,_=fixture_host(tmp_path)
    monkeypatch.setattr(attachment,'process_arguments',lambda pid:args)
    monkeypatch.setattr(attachment,'singleton_process',lambda workspace:123)
    assert attachment.verify_connection_process(host.workspace,123)=='headed'
    with pytest.raises(Exception,match='browser_profile_mismatch'):
        attachment.verify_connection_process(host.workspace,456)


def test_explicit_profile_mismatch_is_not_overridden_by_lock(tmp_path,monkeypatch):
    from job_applier import workspace_attachment as attachment
    host,_,_=fixture_host(tmp_path)
    monkeypatch.setattr(attachment,'process_arguments',lambda pid:['brave','--user-data-dir='+str(tmp_path/'foreign'),'--remote-debugging-port=19600'])
    monkeypatch.setattr(attachment,'singleton_process',lambda workspace:123)
    with pytest.raises(Exception,match='browser_profile_mismatch'):
        attachment.verify_connection_process(host.workspace,123)

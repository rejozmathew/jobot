"""The retained browser must recover without an operator opening the dashboard."""
import os

import pytest

from job_applier import workspace_attachment as attachment


def test_supervisor_reopens_closed_browser_and_reuses_live_profile(tmp_path, monkeypatch):
    from job_applier import workspace_process, workspace_host
    config = {'spool_dir': str(tmp_path/'spool')}
    workspace = {'id': 'synthetic', 'user_data_dir': str(tmp_path/'profile'),
                 'browser_executable': 'synthetic-browser', 'cdp_url': 'http://127.0.0.1:19222',
                 'startup_urls': ['about:blank']}
    pid = [None]
    launches = []
    checked = []
    monkeypatch.setattr(attachment, 'existing_profile_process', lambda _: pid[0])
    monkeypatch.setattr(attachment, 'verify_connection_process', lambda w, p: checked.append(p))
    monkeypatch.setattr(workspace_host, 'endpoint_info', lambda _: {'webSocketDebuggerUrl': 'ws://synthetic'})
    def launch(args, **kwargs):
        launches.append(args)
        pid[0] = 100 + len(launches)
    monkeypatch.setattr(workspace_process, 'detached_launch', launch)
    ticks = []
    def sleep(seconds):
        assert seconds == 5
        ticks.append(seconds)
        if len(ticks) == 2:pid[0] = None  # Browser closes after successful startup.
        if len(ticks) == 4:raise KeyboardInterrupt
    monkeypatch.setattr(attachment.time, 'sleep', sleep)
    with pytest.raises(KeyboardInterrupt):attachment.watch_browser(config, workspace)
    assert len(launches) == 2
    assert all(args[-1] == 'about:blank' for args in launches)
    assert checked == [101, 101, 102, 102]


def test_supervisor_recovers_after_temporary_launch_error(monkeypatch):
    attempts = []
    def ensure(*args):
        attempts.append(True)
        if len(attempts) == 1:raise OSError('synthetic display startup')
        return {'status': 'already_open', 'workspace_id': 'synthetic'}
    monkeypatch.setattr(attachment, 'ensure_browser', ensure)
    def sleep(_):
        if len(attempts) == 2:raise KeyboardInterrupt
    monkeypatch.setattr(attachment.time, 'sleep', sleep)
    with pytest.raises(KeyboardInterrupt):attachment.watch_browser({}, {'id': 'synthetic'})
    assert len(attempts) == 2


def test_supervisor_does_not_replace_a_live_browser_with_unavailable_endpoint(tmp_path, monkeypatch):
    from job_applier import workspace_process, workspace_host
    workspace = {'id': 'synthetic', 'user_data_dir': str(tmp_path/'profile'),
                 'cdp_url': 'http://127.0.0.1:19222'}
    probes = []
    monkeypatch.setattr(attachment, 'existing_profile_process', lambda _: 123)
    monkeypatch.setattr(attachment, 'verify_connection_process', lambda *a: None)
    def endpoint(_):
        probes.append(True)
        raise attachment.ProtocolError('browser_endpoint_not_ready')
    monkeypatch.setattr(workspace_host, 'endpoint_info', endpoint)
    monkeypatch.setattr(workspace_process, 'detached_launch', lambda *a, **k: pytest.fail('must retain live browser'))
    def sleep(_):
        if len(probes) == 2:raise KeyboardInterrupt
    monkeypatch.setattr(attachment.time, 'sleep', sleep)
    with pytest.raises(KeyboardInterrupt):attachment.watch_browser({}, workspace)
    assert len(probes) == 2


def test_manual_and_supervised_launch_share_profile_lock(tmp_path, monkeypatch):
    from job_applier.workspace_process import FileLock
    workspace = {'user_data_dir': str(tmp_path/'profile')}
    monkeypatch.setattr(attachment, '_ensure_browser', lambda *a: pytest.fail('another launch owns the profile'))
    with FileLock(tmp_path/'profile'/'.jobbot-launch.lock'):
        with pytest.raises(attachment.ProtocolError, match='local_lock_busy'):
            attachment.ensure_browser({}, workspace)


def test_existing_browser_lookup_ignores_orphan_chromium_children(tmp_path):
    from job_applier.workspace_linux import linux_profile_in_use
    workspace = {'user_data_dir': str(tmp_path/'profile')}
    for pid, role in [('123', '--type=zygote'), ('124', '--type=renderer')]:
        directory = tmp_path/'proc'/pid
        directory.mkdir(parents=True)
        (directory/'cmdline').write_bytes(('brave\0'+role+'\0--user-data-dir='+workspace['user_data_dir']+'\0').encode())
        (directory/'stat').write_text(pid+' (brave) S 1 2 3')
    assert linux_profile_in_use(workspace, tmp_path/'proc') in (123, 124)
    assert linux_profile_in_use(workspace, tmp_path/'proc', browser_root_only=True) is None
    directory = tmp_path/'proc'/'125';directory.mkdir()
    (directory/'cmdline').write_bytes(('brave\0--user-data-dir='+workspace['user_data_dir']+'\0--remote-debugging-port=19222\0').encode())
    (directory/'stat').write_text('125 (brave) S 1 2 3')
    assert linux_profile_in_use(workspace, tmp_path/'proc', browser_root_only=True) == 125


@pytest.mark.skipif(os.name != 'posix', reason='Linux Chromium singleton timestamps')
@pytest.mark.parametrize('lock_age, socket_exists, expected', [
    (100, False, None),
    (-100, False, 2884),
    (100, True, 2884),
])
def test_singleton_lock_from_before_boot_cannot_claim_reused_pid(
        tmp_path, monkeypatch, lock_age, socket_exists, expected):
    import socket
    from job_applier import workspace_process

    boot = 1700000000
    proc = tmp_path / 'proc'
    proc.mkdir()
    (proc / 'stat').write_text(f'btime {boot}\n')
    profile = tmp_path / 'profile'
    profile.mkdir()
    lock = profile / 'SingletonLock'
    lock.symlink_to(f'{socket.gethostname()}-2884')
    os.utime(lock, (boot - lock_age, boot - lock_age), follow_symlinks=False)
    endpoint = tmp_path / 'process-singleton'
    if socket_exists:
        endpoint.touch()
    (profile / 'SingletonSocket').symlink_to(endpoint)
    monkeypatch.setattr(workspace_process, 'process_identity',
                        lambda pid: {'pid': pid, 'created': 1218})

    from pathlib import Path
    monkeypatch.setattr(attachment, 'Path', lambda path: proc / 'stat' if path == '/proc/stat' else Path(path))
    assert attachment.singleton_process({'user_data_dir': str(profile)}) == expected


@pytest.mark.skipif(os.name != 'posix' or not os.environ.get('JOBBOT_SUPERVISOR_TEST_BROWSER'),
                    reason='Opt-in isolated Linux browser fixture')
def test_real_browser_recovers_without_dashboard(tmp_path):
    import json
    import signal
    import shlex
    import socket
    import subprocess
    import sys
    import time
    import urllib.request
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    launcher = tmp_path/'browser-fixture'
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(os.environ['JOBBOT_SUPERVISOR_TEST_BROWSER'])+' --headless=new "$@"\n')
    launcher.chmod(0o700)
    workspace = {'id': 'supervisor-fixture', 'user_data_dir': str(tmp_path/'profile'),
                 'browser_executable': str(launcher),
                 'cdp_url': f'http://127.0.0.1:{port}', 'mode': 'headless',
                 'startup_urls': ['about:blank']}
    config = {'spool_dir': str(tmp_path/'spool')}
    code = ('import json,sys;from job_applier.workspace_attachment import watch_browser;'
            'watch_browser(*json.loads(sys.argv[1]))')
    def ready(previous=None):
        deadline = time.monotonic() + 25
        observed = None
        while time.monotonic() < deadline:
            pid = attachment.existing_profile_process(workspace)
            if pid and pid != previous:
                try:
                    attachment.verify_connection_process(workspace, pid)
                    with urllib.request.urlopen(workspace['cdp_url']+'/json/list', timeout=1) as response:
                        tabs = json.load(response)
                    observed = tabs
                    if any(t.get('url') == workspace['startup_urls'][0] for t in tabs):return pid, tabs
                except (OSError, ValueError, attachment.ProtocolError) as exc:observed = str(exc)
            assert process.poll() is None, 'Supervisor exited'
            time.sleep(.1)
        pytest.fail('Browser did not recover without dashboard interaction: '+repr(observed))
    with (tmp_path/'supervisor.log').open('w') as log:
        process = subprocess.Popen([sys.executable, '-c', code, json.dumps([config, workspace])],
                                   stdout=log, stderr=log)
        try:
            first, tabs = ready()
            before = {t['id'] for t in tabs}
            # CDP can answer just before the supervisor releases its launch lock.
            deadline = time.monotonic() + 5
            while True:
                try:
                    reused = attachment.ensure_browser(config, workspace, ['about:blank#duplicate'])
                    break
                except attachment.ProtocolError as exc:
                    if exc.code != 'local_lock_busy' or time.monotonic() >= deadline:raise
                    time.sleep(.1)
            assert reused['status'] == 'already_open'
            same, tabs = ready()
            assert same == first and {t['id'] for t in tabs} == before
            attachment.verify_connection_process(workspace, first)
            os.kill(first, signal.SIGTERM)  # This isolated synthetic profile only.
            second, tabs = ready(previous=first)
            assert second != first
            assert not any('60158' in t.get('url', '') for t in tabs)
        finally:
            process.terminate()
            process.wait(timeout=10)
            from job_applier.workspace_linux import linux_profile_in_use, extract_user_data_dir
            # Include orphan children from the intentional main-process exit.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                pid = linux_profile_in_use(workspace)
                if not pid:break
                try:
                    assert extract_user_data_dir(attachment.process_arguments(pid)) == workspace['user_data_dir']
                    group = os.getpgid(pid)
                    assert group != os.getpgrp()
                    os.killpg(group, signal.SIGTERM)
                except ProcessLookupError:pass
                time.sleep(.1)
            assert linux_profile_in_use(workspace) is None, 'Synthetic browser children remain'

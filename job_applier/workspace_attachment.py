"""Process verification, shared-browser setup and retained-browser supervision.

The application host borrows a connection, never the browser process lifetime.
No automation-property overrides or browser-wide cleanup are used.
"""
import ctypes
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time
from urllib.parse import urlsplit

from .managed_shared import ProtocolError


def process_arguments(pid):
    if os.name != 'nt':
        return linux_arguments(Path(f'/proc/{pid}/cmdline').read_bytes())
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         f'(Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}").CommandLine | ConvertTo-Json -Compress'],
        capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ProtocolError('workspace_process_inventory_unavailable')
    command = json.loads(result.stdout or 'null')
    if not command:
        raise ProtocolError('workspace_process_inventory_unavailable')
    argc = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = parse(command, ctypes.byref(argc))
    if not argv:
        raise ProtocolError('workspace_process_inventory_unavailable')
    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(argv)


def linux_arguments(raw):
    args=[a for a in raw.decode('utf-8').split('\0') if a]
    # Chromium can replace argv with a single process-title string on Linux.
    return shlex.split(args[0]) if len(args)==1 and ' --' in args[0] else args


def singleton_process(workspace):
    """Chromium's profile lock identifies its process even with a default profile."""
    from .workspace_process import process_identity
    try:
        profile = Path(workspace['user_data_dir'])
        lock = profile / 'SingletonLock'
        hostname, pid_text = os.readlink(lock).rsplit('-', 1)
        pid = int(pid_text)
        if hostname != socket.gethostname() or not process_identity(pid):
            return None

        # Chromium stores only a PID. After a reboot that number can belong to
        # a different process. Retain the lock if the singleton endpoint exists
        # or the boot time cannot be established.
        try:
            boot = next((int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                         if line.startswith('btime ')), None)
            if boot is not None and lock.lstat().st_mtime < boot:
                try:
                    (profile / 'SingletonSocket').stat()
                except FileNotFoundError:
                    return None
        except (OSError, ValueError):
            pass
        return pid
    except (OSError,ValueError):pass
    return None


def existing_profile_process(workspace):
    if os.name != 'nt':
        from .workspace_linux import linux_profile_in_use
        # Chromium children may outlive a closed browser. Only its main process
        # can own the retained connection and prevent automatic relaunch.
        return singleton_process(workspace) or linux_profile_in_use(workspace, browser_root_only=True)
    from .workspace_host import profile_in_use
    return profile_in_use(workspace)


def verify_connection_process(workspace, pid):
    """Match configured profile and debugging port without getBrowserCommandLine.

    That CDP method itself requires --enable-automation. OS inventory doesn't.
    """
    from .workspace_linux import extract_user_data_dir
    args = process_arguments(pid)
    profile = extract_user_data_dir(args)
    normalize = lambda p: os.path.normcase(str(Path(p).resolve()))
    if (profile and normalize(profile) != normalize(workspace['user_data_dir'])) or (not profile and singleton_process(workspace)!=pid):
        raise ProtocolError('browser_profile_mismatch')
    flags = {}
    for index, arg in enumerate(args):
        if arg.startswith('--'):
            key, sep, value = arg.partition('=')
            flags[key] = value if sep else (args[index+1] if index+1 < len(args) and not args[index+1].startswith('--') else True)
    if str(flags.get('--remote-debugging-port')) != str(urlsplit(workspace['cdp_url']).port):
        raise ProtocolError('browser_endpoint_mismatch')
    mode = 'headless' if '--headless' in flags else 'headed'
    if mode != workspace.get('mode', 'headed'):
        raise ProtocolError('browser_mode_mismatch')
    return mode


def launch_arguments(workspace, urls):
    """A manual launch with fixed loopback debugging, without automation flags."""
    return [workspace['browser_executable'], '--user-data-dir='+workspace['user_data_dir'],
            '--remote-debugging-address=127.0.0.1',
            '--remote-debugging-port='+str(urlsplit(workspace['cdp_url']).port),
            '--no-first-run', '--no-default-browser-check', *urls]


def ensure_browser(config, workspace, urls=None):
    """Reuse the configured browser or launch it once, including concurrent callers."""
    from .workspace_process import FileLock
    with FileLock(Path(workspace['user_data_dir'])/'.jobbot-launch.lock'):
        return _ensure_browser(config, workspace, urls)


def _ensure_browser(config, workspace, urls):
    from .application_runtime import REPOSITORY
    from .workspace_host import endpoint_info
    from .workspace_process import detached_launch
    # A second click on the launcher must not duplicate dashboard/mail tabs.
    pid = existing_profile_process(workspace)
    if pid:
        verify_connection_process(workspace, pid)
        endpoint_info(workspace['cdp_url'])
        return {'status':'already_open','workspace_id':workspace['id']}
    urls = urls or workspace.get('startup_urls') or ['about:blank']
    log = Path(config['spool_dir'])/'shared-browser.log'
    detached_launch(launch_arguments(workspace, urls), cwd=REPOSITORY, stdout_path=log, stderr_path=log)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            pid=existing_profile_process(workspace)
            if pid:
                verify_connection_process(workspace,pid)
                endpoint_info(workspace['cdp_url'])
                break
        except (OSError,ValueError,ProtocolError):pass
        time.sleep(.2)
    else:
        raise ProtocolError('browser_endpoint_not_ready',
            'Close Brave once and reopen it with this launcher. An already-running browser ignores new debugging launch options; your tabs have not been closed.')
    return {'status':'launched','workspace_id':workspace['id']}


def watch_browser(config, workspace, urls=None):
    """Recover a closed retained browser independently of dashboard visits."""
    previous = None
    while True:
        try:
            result = ensure_browser(config, workspace, urls)
        except (OSError, ValueError, ProtocolError) as exc:
            # A starting display, busy launcher or temporarily unavailable endpoint
            # is retried; never kill/reconfigure an existing profile to recover it.
            result = {'status':'waiting','workspace_id':workspace['id'],
                      'reason':getattr(exc, 'code', type(exc).__name__)}
        if result != previous or result['status'] == 'launched':
            print(json.dumps(result), flush=True)
        previous = result
        time.sleep(5)


def main():
    import argparse
    from .application_runtime import resolve_config, validate_workspaces
    parser = argparse.ArgumentParser(description='Open or supervise the configured shared browser; application runs attach without owning its lifetime.')
    parser.add_argument('--config')
    parser.add_argument('--workspace')
    parser.add_argument('--watch', action='store_true', help='Keep the retained browser available after it closes.')
    parser.add_argument('urls', nargs='*')
    args = parser.parse_args()
    config = resolve_config(args.config)
    workspaces = validate_workspaces(config['workspaces'])
    workspace = next(w for w in workspaces if w.get('connection_mode') == 'existing' and (not args.workspace or args.workspace == w['id']))
    if args.watch:
        watch_browser(config, workspace, args.urls)
    else:
        print(json.dumps(ensure_browser(config, workspace, args.urls)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

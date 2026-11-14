# Operations and troubleshooting

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Contributing](../CONTRIBUTING.md)

## Identify the installation first

The authoritative Ubuntu runtime and the Windows engineering checkout can have
different filesystem paths and deliberate deployed overlays. Use the existing
private runtime config and deployment records. Do not infer history from the root
`job_applier.db`, copy a Windows profile over Ubuntu, or replace the deployed tree
with an unrelated checkout.

The tracked [systemd templates](../deploy/systemd/) use example home-relative paths.
Installed unit files describe the actual checkout, interpreter, environment and
display. Examples below assume the existing user's service manager.

## Service map

| Unit / process | Function | Consequence if unavailable |
|---|---|---|
| `jobbot-dashboard.service` | `queue_runtime serve`; API, UI and answer learner | No dashboard/learning process; independent queue work may continue |
| `jobbot-queue.service` | `queue_runtime watch` | New saved requests wait; inspect existing executor ownership before changing processes |
| `jobbot-browser.service` | Persistent retained-browser supervisor during graphical login | Reopens a closed browser; desktop queue waits for readiness without consuming requests or application deadlines |
| Workspace host(s) | Per-workspace owned browser operations and supervision | Browser readiness or session recovery needs investigation |
| Retained browser launcher | Configured existing browser profile and CDP | Existing-mode applications cannot attach until available |
| `jobbot-harvest.timer` / `.service` | Schedule separate discovery runs | No scheduled discovery; existing intake remains |
| `jobbot-notifications.service` | Optional confirmed-submission observer | Alert delivery waits; application outcomes remain durable |
| `jobbot-validation-cleanup.timer` / `.service` | Remove completed registered disposable fixtures | Test storage can accumulate; production artifacts have separate retention |
| `jobbot-storage-maintenance.timer` / `.service` | Bound download/build caches and compress/expire verified backup copies | Disposable cache and raw backup storage can accumulate |

The queue unit's historical description may say “sequential”; the current
dispatcher implements the operator-selected concurrency. The selected settings
and code determine behavior, not the unit's display name.

### Desktop startup ordering

For an existing-browser Hermes desktop installation, install the adapted
[`jobbot-browser.service`](../deploy/systemd/jobbot-browser.service) and
[`existing-browser.conf`](../deploy/systemd/jobbot-queue.service.d/existing-browser.conf)
queue drop-in in the existing user service directory. Use the installation's
checkout/interpreter and private config. Enable the browser unit for
`graphical-session.target`; keep one existing Hermes desktop autostart entry.
Disable any duplicate browser desktop-autostart entry for that same profile.
Reload the user service manager and start the browser unit at an idle boundary.
It runs `workspace_attachment --watch`, checks every five seconds, and reopens
the configured profile when its browser process disappears. It reuses a correctly
configured running browser without duplicating its tabs. Transient launch or
endpoint failures are retried and reported on state changes in the unit journal.
An existing process with an unavailable endpoint is retained, not killed.
On Linux, a local Chromium singleton lock from before the current boot with a
missing singleton socket does not identify the current process at that PID.
The supervisor falls back to its normal profile process checks and launch path.
It does not delete the singleton files or close any existing browser tabs.
The unit should show `active (running)`, not the old `active (exited)` state.
Do not restart this browser unit while applications are active: it owns browsers
it launches, whereas starting it against an already-open browser only adopts the
connection. The desktop session supplies the display and authorization environment.

Opening or closing the dashboard tab does not start or stop scheduling. The
browser supervisor operates independently of dashboard visibility and does not
pause work while answers are being entered. Closing the whole retained browser
causes it to reopen; use the existing queue controls to pause application work.

The queue stays online while Hermes is starting and shows a specific startup
wait in the dashboard. It checks the native backend with a short, read-only RPC
and verifies the configured retained browser before reserving a ready request.
Startup waits retain request IDs, wake requests and retry timing; they do not
consume attempts or start application deadlines. Checks repeat automatically
without a new retry limit. Existing application supervision continues normally.
Managed browser workspaces and other executor transports retain their existing
startup path. This ordering does not make a logged-out graphical desktop available
or solve memory exhaustion; inspect the desktop and kernel logs for those failures.

## Read-only health checks

Workspace hosts launch with the repository virtualenv when installed and ignore
inherited Python environment overrides. This keeps a harness's `PYTHONPATH` or
`PYTHONHOME` from loading packages compiled for a different interpreter. Display,
configuration and other non-Python environment values remain available. Existing
hosts are retained until their normal idle exit; launching a clean caller alone
does not repair dependencies already imported by a running host.

```bash
systemctl --user status jobbot-dashboard.service jobbot-queue.service
systemctl --user list-timers jobbot-harvest.timer jobbot-validation-cleanup.timer
systemctl --user cat jobbot-dashboard.service jobbot-queue.service
journalctl --user -u jobbot-queue.service --since '30 minutes ago' --no-pager
./.venv/bin/python -m job_applier.queue_runtime --config /absolute/runtime.json status
./.venv/bin/python -m job_applier.application_runtime sessions --config /absolute/runtime.json
```

Keep config paths, log output and application details private. `queue_runtime doctor`
checks executable/display/configuration presence; it does not establish authenticated
mail access, Simplify functionality or employer acceptance. `application_runtime doctor`
is optional diagnostic inspection, not another prerequisite before each application.

On Windows use the repository `.venv\Scripts\python.exe` and the existing private
launcher. See the [Windows runbook](jobbot-v1/WINDOWS_RUNBOOK.md) for its historical
provisioning details; current runtime entry points are in [Getting started](GETTING_STARTED.md).

## Scheduling controls

For company/title matching, configure the private `duplicate_matching` endpoint
and model, then inspect `duplicate_matches` in shadow mode before selecting
**Skip high-confidence applied duplicates** in Settings. Migration 29 is additive
and receives the ordinary `prepare_local` backup. Reload affected idle dashboard,
queue and workspace processes through the deployment workflow; do not replace
an active application to load matching code. Intake inference and the dashboard
background worker fill the shared cache. Model outages retain cached/exact
matching and do not block application work.

The daily Discord report belongs to the existing `jobbot-notifications.service`.
Set `submission_notifications.daily_summary` to the approved time and timezone
and restart that observer. Retain `notifications/submissions.json`; deleting it
loses delivery history. Preview counts with `python -m job_applier.daily_summary`
before rollout, and inspect the next report date in the private receipt file.
Changing report configuration does not require restarting application browsers.

```bash
# Global persistent pause: current admitted work drains normally.
./.venv/bin/python -m job_applier.queue_runtime --config /absolute/runtime.json pause-all
./.venv/bin/python -m job_applier.queue_runtime --config /absolute/runtime.json resume-all

# Automatic pickup only; explicit manual requests remain a separate path.
./.venv/bin/python -m job_applier.queue_runtime --config /absolute/runtime.json pause
./.venv/bin/python -m job_applier.queue_runtime --config /absolute/runtime.json resume
```

`run-next` wakes existing ready queue work. `once` directly runs a dispatch loop
iteration and should not be started beside the installed watcher. Both use a
per-instance dispatcher lock. Normal operation uses one watcher.

Individual session Pause, Stop and Restart use the application's owned lifecycle.
Do not terminate the shared browser to fix one job. Lowering concurrency does not
evict admitted work. Pausing automatic pickup is not the same as pausing all new
manual and discovery work.

## Diagnosing a problem

| Symptom | Likely boundary | First useful checks |
|---|---|---|
| Empty or unexpected job history | Wrong runtime/configuration | Instance ID, resolved `db_path`, current versus legacy server |
| UI works; jobs wait | Dispatcher/schedule/capacity | Worker online state, global pause, automatic setting, due times and active cleanup |
| Queue says it is waiting for Hermes/browser startup | Desktop dependencies | Native backend, graphical session, browser unit and its CDP/profile connection; queued requests remain intact |
| Manual request is saved but waits | Global pause or occupied capacity | Banner, earlier explicit requests and active windows |
| Existing browser cannot attach | Browser launch/profile/CDP | Configured launcher, loopback endpoint, profile path and browser process |
| Recovery seems stuck | Current owned page or pending lifecycle operation | Session status, fresh screenshot actually inspected, overlays/frames and available recovery |
| Application ended at a consistent duration | Overall deadline | Attempt snapshot, `application_time_limit` reason and original dispatch start |
| SQLite BUSY/LOCKED appears | Concurrent bookkeeping | Bounded transaction logs, worker continuity, disk health and current source; retain owned executors |
| Required answers remain pending | Question/answer mapping | Exact current choices, saved response scope, conflicting knowledge and retry state |
| AI learning is unavailable | Dashboard learner/provider | Dashboard process, learning activity, installed auxiliary inference credentials |
| Discovery found nothing or ended incomplete | Discovery executor/intake | Recorded discovery status, saved outputs and source attribution; distinguish no matches from failure |
| Confirmation alert missing | Optional observer/delivery | Submission ledger, new versus already-applied outcome, private receipt and observer logs |
| Browser windows remain after an attempt | Owned-target cleanup | Session/dispatch state, process identity and pending cleanup; do not close unrelated tabs |

For browser recovery, follow the canonical application procedure. A helper miss,
an exhausted helper slice or an old Submit click is not a new finish rule. Before
concluding an unresolved obstacle, inspect a fresh owned screenshot and attempt
remaining plausible supported recovery within the selected deadline.

For engineering diagnosis, retrieve the attempt report, event/action timeline,
source/version evidence and relevant private captures. Separate runtime defects,
employer obstacles, missing user information and operator intervention. Do not
change production records to reproduce a test.

## Backups and migrations

The selected instance must match its configuration. Runtime preparation backs up
before additive migrations. Managed tools provide explicit backup and copy-migrate
operations:

```text
python run_applier.py managed backup --source /absolute/managed.db --destination /absolute/new-backup.db --instance-id EXISTING_INSTANCE_ID
python run_applier.py managed preview-new --db /absolute/new-development.db
```

Use a new destination and record its identity/hash. For active SQLite databases,
use the backup API/tool rather than copying only the main `.db` while WAL writes
may exist. Preserve private assets, account references and evidence independently
of the code release. A code rollback is not permission to restore an older database.

## Validated deployment workflow

Repository instructions authorize deployment of completed, tested changes to the
existing authoritative Ubuntu runtime. They do not authorize replacing private
configuration, discarding unrelated deployed changes or pushing unrelated remotes.

1. Review the exact diff and validate it. Commit the local checkpoint. Record the
   source commit, intended file list and validation evidence.
2. Inspect deployed file hashes, installed services and private deployment notes.
   Account for intentional Ubuntu-only overlays before composing a file-scoped
   deployment. Back up every file that will change.
3. For runtime changes, pause new pickup as needed and let active applications
   finish. Record prior queue/discovery state. Never kill an application to obtain
   an idle deployment window.
4. Apply only the intended files, verify their hashes and perform any existing
   migration procedure with its backup. Preserve profiles, credentials, databases,
   browser cookies, evidence and unrelated changes.
5. Reload/restart only affected idle processes. A queue-service stop may terminate
   its process group, so do not treat restart as harmless during active work.
   Pure reference-document changes normally require no service restart.
6. Verify source hashes and affected services, perform appropriate synthetic
   checks, then restore the recorded pickup state. Save the deployment manifest,
   backups and verification results privately.

Static UI files are served from disk; a pure asset update may need only a browser
refresh, as appropriate to that release. Python processes retain imported code
until reloaded. Decide from the changed component rather than restarting everything.

For self-improvement reviews, use the additional numbered label/tag/report workflow
in [SELF_IMPROVEMENT.md](jobbot-v1/SELF_IMPROVEMENT.md). Do not infer production
performance improvements from a synthetic test count.

## Rollback

Use the deployment manifest's file-scoped backups and prior service/pickup state.
Wait for an appropriate idle boundary for executable changes, restore only those
files, and verify hashes and service health again. Keep newer application history
and evidence. Additive database changes require compatibility review; an older
binary must not be assumed safe against every later schema.

If a deployed overlay or unexpected file change prevents a clean update, preserve
it and resolve the diff. Do not use a whole-tree reset or checkout overwrite as a
deployment mechanism.

## Private validation storage

Synthetic browser fixtures, temporary profiles and test databases live in isolated
private directories. Logs/JUnit and completion metadata must live outside disposable
fixture directories. Ubuntu cleanup removes completed registered fixtures after
the documented retention interval and verifies process ownership first.

Follow [Validation storage](jobbot-v1/VALIDATION_STORAGE.md). Never apply its fixture
cleanup rules to production browsers, current application evidence or private
configuration.

## Runtime storage maintenance

The separate `scripts/maintain_runtime_storage.py` command operates on the
selected private runtime config. Preview with:

```bash
./.venv/bin/python scripts/maintain_runtime_storage.py --runtime-config /absolute/runtime.json
# Review the preview, then add --apply for the same scope.
```

The fixed allowlist covers pip, Electron, node-gyp and npm download caches,
Hermes desktop packaging inputs/tools, and the separate Brave disk-cache folder.
Files expire after seven days (fourteen for node-gyp); per-folder limits are
64–256 MiB, with oldest files evicted first. Active build/download processes
defer cache cleanup; a running browser defers browser-cache cleanup. Running
executables, Hermes release folders, installed dependencies, browser profiles,
cookies, live databases and conversation history are outside this cache allowlist.

The installed service also opts into `--dispose-completed-output`. This separately
deletes scratch files (including old compressed scratch copies) for discovery runs
with a recorded end time. It retains `records.json`, `checkpoint.json`,
`result.json` and `model-selection.json`; the database retains intake, provenance
and application outcomes. Unknown run directories are retained. The discovery
lock prevents cleanup overlapping discovery and its checkpoint handoff. The
Linux service uses standard-library `fcntl.flock` on the same lock file, so the
entry point requires no third-party lock package. End-to-end CLI regressions run
with Python site packages disabled and cover both idle and busy discovery.

The same option deletes screenshots older than one day and older than every
still-open application session, plus files older than one day in Hermes' main
and discovery-profile scratch, terminal-output, exec, web, browser-use,
screenshots, spillover and delegation cache directories. Process-referenced
directories, symlinks, hard-linked files and changing files are retained. An
unreadable process command defers this sweep. These are permanent deletions:
historical screenshot views and old spilled tool outputs may become unavailable.
Current recovery screenshots, active discovery output, credentials, approved
facts and job/account/submission records remain intact. This does not change
application deadlines or recovery behavior.

Explicitly named database backup copies under `private-spool/deployments`,
`managed.db.before-local-*.db` beside the selected database, and Hermes
`state.db.pre-update-*.bak` backups are compressed after two days. Compression
verifies the entire decompressed SHA-256 and checks the original is unchanged
before removing its raw copy. A `.gz.storage.json` receipt records both hashes.
SQLite sidecars, process references, changed files, symlinks and unknown backup
names are retained. Previously registered archives expire after thirty days,
always keeping the newest three distinct snapshots in each category (Jobot
deployments, Jobot local snapshots, main Hermes, discovery Hermes). Source
backups and deployment manifests themselves remain available.

Restore a compressed backup to a **new** path with `gzip -dc backup.db.gz >
/absolute/new-copy.db`, verify its SHA-256 against `source_sha256` in the receipt,
then follow the normal database recovery procedure. Never restore over a live
database or replace newer application history. Older deployment manifests may
name the original uncompressed filename; its verified `.gz` counterpart holds
the same bytes during retention.

The adapted `jobbot-storage-maintenance.service` and `.timer` run hourly with
low CPU/I/O priority and a single-run lock. They do not stop queue work or change
application eligibility. Install them in the existing user's systemd directory,
reload the user manager and enable the timer. The latest private result is
`~/.local/state/jobbot-storage/latest.json`; inspect it and the service journal
for errors, retained active caches and the `low_space` indicator (less than 4 GiB
available). This complements the existing validation-fixture cleanup timer.

Preserved conversation and application history can still grow. Discovery scratch
is temporary working data rather than a durable archive. Minimal checkpoint and
intake records intentionally remain after cleanup. Hermes conversation databases
are separate: their native ended-session pruning and safe idle compaction are
needed to reclaim transcript storage. This command does not prune those databases
or stop their holders. It does not promise a fixed total disk size.

For a dedicated disposable discovery profile, Hermes' native `sessions` settings
can use `auto_prune: true`, `retention_days: 0`, `min_interval_hours: 1`,
`vacuum_after_prune: true` and `min_vacuum_interval_days: 1`. This deletes ended,
unpinned discovery transcripts on a subsequent maintenance/startup pass while
protecting live turns and open continuation chains. Apply this only to the
discovery profile, not a shared personal conversation profile. Native compaction
defers while another process holds the database; deleted pages can be reused
before the file's physical size shrinks. Do not remove an open SQLite database
or its WAL/SHM files to force disk reclamation.

## Preparing a public repository

The public source tree contains neutral templates; filled profiles, credentials,
resumes, browser data and application evidence belong in private storage. Run
`python scripts/check_public_tree.py` in the repository virtual environment before
publication. It checks tracked filenames and obvious credential patterns and
does not read ignored operator files. Use a full secret scanner as well, including
all branches and tags; inspect findings without copying secret values into reports.

Deleting a file in a new commit does not remove it from Git history. If credentials
were committed, rotate them wherever used and sanitize every published reference
before changing visibility. Preserve a private recovery bundle and a mapping of
old to rewritten commits/tags. A coordinated history rewrite changes commit IDs
and requires existing clones to resynchronize; obtain approval for that destructive
Git operation. Preserve active runtime files and databases separately from the
source history rewrite. GitHub pull-request references or cached commits may need
additional host-side removal; a branch-only scan cannot certify those copies.

The October 2026 cleanup removes obsolete root probes and personal backup files
from the maintained source, groups historical narrative under `docs/legacy/`, and
adds `profile.json.template`. Runtime rollout preserves existing private files even
when their former copies are removed from version control. These publication
checks do not add restrictions to application execution.

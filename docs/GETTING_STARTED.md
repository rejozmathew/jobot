# Getting started

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Operations](OPERATIONS.md)

## First-time personal installation

This section is for a new person setting up their own Jobot installation. It was
checked against the repository on October 15, 2026. Setup is hands-on: the
repository supplies the runtime, dashboard, helpers and application skills;
Hermes, model access, Simplify, mail authentication and Discord are separate.
Use your own data and accounts. An existing operator's database, browser cookies,
private configuration and old profile backups are not installation templates.

| Component | What to prepare |
|---|---|
| Computer | Windows or Ubuntu with Git, Python 3.11 and a graphical Chrome/Chromium session; Ubuntu services need access to that desktop/display |
| Hermes | Install separately, authenticate a model provider and enable terminal, file/skill tools and screenshot/vision support |
| Candidate | Your factual profile, application email address, preferences and a local resume file |
| Simplify | Your own account and completed profile, plus the official Copilot extension in the browser profile Jobot actually uses |
| Email | Authenticated access to the mailbox receiving employer verification messages; Himalaya or the supported Hermes Gmail wrapper |
| Discord | Optional: your own bot/server/channel for conversations or submission alerts |

### 1. Get the code and Python environment

The public repository's maintained application is on `main`; cloning over HTTPS
does not require a GitHub account. Hermes, your model provider, email and Simplify
still require their own installation and authentication.

```text
git clone https://github.com/rejozmathew/jobot.git Jobot
cd Jobot
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-jobbot-lock.txt
```

Ubuntu:

```bash
python3.11 -m venv .venv
./.venv/bin/python -m pip install -r requirements-jobbot-lock.txt
```

All following commands run from the checkout root. `<python>` means the absolute
path to this virtual environment's Python, not Hermes's interpreter. The managed
runtime does not require installing the legacy `requirements.txt`. Keep the
checkout in a local directory, such as `C:\GitClone\Jobot` or `~/git/Jobot`.

### 2. Install and authenticate Hermes

Follow the official [Hermes quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/).
Run `hermes setup`, select your provider/model and confirm a normal chat works.
Use `hermes tools` to check terminal and file/skill access. The executor must also
be able to inspect screenshots. Use a local terminal backend on the machine
holding the Jobot checkout, browser and private files; a remote/container backend
needs those resources explicitly provisioned there.

If using a named Hermes profile, use that same profile for these setup steps,
the executor command, mailbox access and any gateway/notification configuration.
Model authentication belongs to Hermes; it is not bundled with Jobot.

### 3. Create your private profile, resume and runtime

Start with the downloadable [profile.json.template](../profile.json.template).
It contains the supported profile fields with blank strings, empty lists and
`null` for unanswered numbers/yes-no questions. It contains no sample career,
immigration, demographic or consent answers. `profile.example.json` is an
identical compatibility copy; maintain the template as the field reference.

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force artifacts/jobbot-v1-private/my-install
if (Test-Path artifacts/jobbot-v1-private/my-install/candidate.json) { throw 'Keep your existing profile; choose another installation directory.' }
Copy-Item profile.json.template artifacts/jobbot-v1-private/my-install/candidate.json
```

Ubuntu:

```bash
mkdir -p artifacts/jobbot-v1-private/my-install
cp -n profile.json.template artifacts/jobbot-v1-private/my-install/candidate.json
chmod 700 artifacts/jobbot-v1-private/my-install
chmod 600 artifacts/jobbot-v1-private/my-install/candidate.json
```

Use a new installation directory; preserve any existing profile. Open your private
`candidate.json` and enter your name, contact information, location, target roles,
skills, work history and education. Repeat the experience/education objects for
each entry, or remove unused entries. Replace `you@example.com`. Answer work
authorization and sponsorship from your own circumstances. Choose voluntary
self-identification and consent answers yourself. Remove unanswered fields or
leave them null; null means unknown, not “no.” Keep dates and factual answers
consistent with your resume and Simplify profile.

Put your approved resume at `artifacts/jobbot-v1-private/my-install/resume.pdf`.
The template's relative resume path is resolved beside the profile. The setup
below imports factual fields and registers that file; credentials are not imported
into the candidate record. Leave the template's `accounts` passwords blank and
configure employer credentials separately below. Never commit the filled profile.
An OS-private directory outside the checkout also works if you update the paths.

Save the following as `artifacts/jobbot-v1-private/setup_my_jobot.py`, edit the
browser and Hermes executable paths for your machine, then run it once with
`<python> artifacts/jobbot-v1-private/setup_my_jobot.py`. It uses existing Jobot
service APIs to create a new database, import the profile and register the resume
with its real file hash. It does not launch a browser or apply to a job.

```python
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

repo = Path.cwd().resolve()  # Run from the Jobot checkout root.
sys.path.insert(0, str(repo))
from job_applier.managed import Service

private = repo / "artifacts/jobbot-v1-private/my-install"
private.mkdir(parents=True, exist_ok=True)
if os.name != "nt":
    private.chmod(0o700)
browser = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe") if os.name == "nt" else Path("/usr/bin/google-chrome")
hermes = Path(r"C:\REPLACE\hermes.exe") if os.name == "nt" else Path("/home/REPLACE/.local/bin/hermes")
assert browser.is_file() and hermes.is_file(), "Set your browser and Hermes paths"
profile = json.loads((private / "candidate.json").read_text(encoding="utf-8"))
resume = (private / "resume.pdf").resolve()
resume_hash = hashlib.sha256(resume.read_bytes()).hexdigest()
assert not any((private / n).exists() for n in ("managed.db", "runtime.json", "auth.json")), "Use a new installation directory; preserve existing state"
service = Service.create(private / "managed.db", instance_id="my-jobot")
candidate = service.import_profile(profile)
asset = service.register_asset(identity_id=candidate["identity_id"], kind="resume",
    version="initial", storage_ref=resume.as_uri(), sha256=resume_hash,
    provenance={"source": "candidate-provided"})
auth_path = private / "auth.json"
auth_path.write_text(json.dumps({"operator": secrets.token_urlsafe(32),
    "worker": secrets.token_urlsafe(32)}), encoding="utf-8")
if os.name != "nt":
    auth_path.chmod(0o600)
config = {
    "transport": "local", "instance_id": "my-jobot",
    "db_path": str(private / "managed.db"),
    "identity_id": candidate["identity_id"], "resume_asset_id": asset["id"],
    "spool_dir": str(private / "spool"),
    "base_url": "http://127.0.0.1:60158",
    "operator_token_env": "JOBBOT_OPERATOR_TOKEN",
    "worker_token_env": "JOBBOT_WORKER_TOKEN", "worker_id": "local-hermes",
    "credential_files": {
        "JOBBOT_OPERATOR_TOKEN": {"path": str(auth_path), "key": "operator"},
        "JOBBOT_WORKER_TOKEN": {"path": str(auth_path), "key": "worker"}
    },
    "hermes_command": [str(hermes), "chat", "--query-file", "{prompt_file}"],
    "require_simplify": True, "legacy_history_paths": [],
    "workspaces": [{"id": "personal-browser",
        "user_data_dir": str(private / "browser-profile"),
        "browser_executable": str(browser), "cdp_url": "http://127.0.0.1:9222",
        "mode": "headed", "connection_mode": "existing"}]
}
config_path = private / "runtime.json"
config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
print("Created runtime:", config_path)  # Never print the token values.
```

On Windows, restrict the private folder to your OS account using its Security
properties. Keep these files out of Git and shared/synced folders. The generated
HTTP tokens are for the dashboard/API; ordinary local application startup does
not need to send a token. This creates the existing development/review defaults.
Change mode and submission choices deliberately in Settings when ready to submit.

Select the resulting absolute configuration path in each terminal/service:

```powershell
$env:JOBBOT_CONFIG = 'C:\GitClone\Jobot\artifacts\jobbot-v1-private\my-install\runtime.json'
```

```bash
export JOBBOT_CONFIG="$PWD/artifacts/jobbot-v1-private/my-install/runtime.json"
```

Alternatively, put `{"config_path":"ABSOLUTE_PATH_TO_RUNTIME_JSON"}` in the
ignored `artifacts/jobbot-v1-private/runtime-config.json` pointer. JSON Windows
paths need escaped backslashes or forward slashes. Do not replace an existing
installation's pointer. Named Hermes profiles can add `--profile`, `PROFILE_NAME`
before `chat` in `hermes_command`; verify supported flags with `hermes chat --help`.

Employer account credentials are separate from the factual profile and HTTP
tokens. When using the built-in credential filler, set `credential_profile_path`
to an absolute private JSON file containing `accounts.default.email` and
`accounts.default.password` for your intended employer-account login. The email
must match the candidate. Existing saved account references can use
`credential_account_keys` to select other entries. Do not use your mailbox password
as an employer-account password. See the canonical
[account and mail procedure](../skills/productivity/job-apply/references/accounts-and-mail.md).
Leave `answer_policy_profile_path` unset unless that file contains an explicitly
populated `application_answer_policy`; copying an empty policy reference fails validation.

### 4. Set up the actual browser and Simplify profile

Run `<python> -m job_applier.workspace_attachment --config ABSOLUTE_RUNTIME_JSON`.
This opens the configured retained browser with its own profile and local CDP
endpoint. In **that browser**, install the official
[Simplify Copilot extension](https://simplify.jobs/copilot), sign in, and complete
your identity, work history, education, preferences and resume selection. Follow
[Simplify's setup guide](https://help.simplify.jobs/en/help/articles/1749022-installing-and-setting-up-copilot).

Verify the extension opens and shows your account. Installing it in your normal
Chrome profile does not install it in Jobot's separate profile. Keep this browser
available for existing-mode sessions. Jobot and Simplify have separate profile
stores: update both when your facts/resume change. Jobot registers a resume for
upload; it does not reconstruct your Simplify history from the PDF during a run.
Keep CDP at `127.0.0.1`; on Ubuntu, the browser needs an available graphical session.

### 5. Connect Hermes to the repository

**All Jobot-specific skills are included in the clone:**

| Repository path | Purpose |
|---|---|
| [`integrations/hermes_jobbot/skills/job-apply/SKILL.md`](../integrations/hermes_jobbot/skills/job-apply/SKILL.md) | Thin Hermes entry; finds the checkout and reads the canonical procedure |
| [`skills/productivity/job-apply/`](../skills/productivity/job-apply/) | Full shared application procedure and ATS/account references |
| [`skills/productivity/workday-simplify/`](../skills/productivity/workday-simplify/) | Workday/Simplify procedure |
| [`skills/job-posting-harvest/`](../skills/job-posting-harvest/) | Optional discovery procedure |
| [`integrations/hermes_jobbot/`](../integrations/hermes_jobbot/) | Optional native `jobbot` tool plugin |

The simplest route is the entry skill plus the portable CLI. In the active Hermes
profile's `config.yaml`, merge this into its existing `skills` section:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/Jobot/integrations/hermes_jobbot/skills
```

On Windows use a quoted forward-slash path such as
`'C:/GitClone/Jobot/integrations/hermes_jobbot/skills'`. Retain existing entries.
Start a fresh Hermes chat and use `hermes skills list` to check `job-apply` appears.
If another copy shadows it, inspect its location and deliberately select the
repository entry. Older Hermes versions can copy this entry's whole `job-apply`
directory into the active profile's `skills/` directory; refresh that copy when
updating Jobot. The [Hermes skills guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
documents discovery and precedence.

Set the Hermes project's working directory to this checkout and provide the
absolute runtime configuration path (or install the local pointer above). Ask:

> Use Jobot at MY_CHECKOUT with MY_RUNTIME_JSON. Read its job-apply entry and
> canonical skill. Confirm the configured paths and skill are accessible; do not
> start an application yet.

The skill is instructions, not a Python installation. Keep the entire checkout;
downloading only `SKILL.md` does not supply its helpers or referenced procedures.
For application requests, Hermes follows the canonical CLI and uses its actual
conversation ID, with `--wait-seconds 0`. No extra model is launched by that CLI.

**Optional native tool:** install the directory `integrations/hermes_jobbot` as a
local plugin using the installed Hermes plugin manager. Check
`hermes plugins install --help` for that version's local-path syntax. In the
plugin's settings set `app_repo` to the absolute checkout and `app_config` to the
absolute runtime JSON; enable the plugin identified by its manifest as
`jobbot-worker`. Current Hermes stores these under
`plugins.entries.<plugin-id>.settings` and exposes them in Desktop plugin settings.
Reload/restart that Hermes process and confirm `jobbot` is available. Keep the
entry skill discoverable separately; installing the plugin alone does not prove
the skill was indexed. The [Hermes plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/)
describes installation/settings; [the adapter reference](jobbot-v1/HERMES_INTERFACE.md)
records the interface originally validated here. If versions differ, the portable
CLI route remains available without a native plugin.

### 6. Connect your application mailbox

Mail access lets the executor retrieve employer verification codes/links. It is
different from receiving chat messages by email. Use your own application inbox;
a Discord bot connection does not authorize reading that mailbox.

**Himalaya route:** Hermes supplies the `himalaya` skill; install the separate
Himalaya CLI and authenticate an account according to that skill. In Hermes,
ask it to configure the skill for your application inbox, then verify a read-only
listing of that account. If missing, find it in the official
[bundled skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog/).
The [upstream email setup guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/agent-email-address.md)
explains the mailbox setup. Add these fields to your private runtime JSON:

```json
{
  "mailbox_provider": "himalaya",
  "himalaya_executable": "/absolute/path/to/himalaya",
  "himalaya_account": "YOUR_CONFIGURED_ACCOUNT_NAME",
  "himalaya_config_path": "/absolute/path/to/himalaya/config.toml"
}
```

**Gmail alternative:** install/enable Hermes's `google-workspace` skill and finish
its Gmail OAuth setup for your own account. The existing Jobot Gmail wrapper
expects the skill's Python `scripts/google_api.py` interface with `main()` and
`TOKEN_PATH`. Set `mailbox_provider` to `gmail`, `gmail_script` to that installed
script's absolute path, and `mailbox_token_path` to the authenticated token file.
Check your installed skill actually provides that interface; a newer CLI-only
integration is not automatically compatible. Use Himalaya if it does not.

Confirm the mailbox address matches the intended candidate and a read-only query
works. File/executable presence alone is not authentication. Where using forwarded
mail, configure the explicit `email_route` described in
[Integrations](INTEGRATIONS.md#mailbox-and-account-verification). Keep OAuth files,
app passwords and message contents private. Jobot does not ship these email skills
or credentials; they come from your Hermes installation and mail provider.

### 7. Optional Discord bot and submission alerts

For bot conversations, follow the official
[Hermes Discord guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord/):
create your own Discord application/bot, enable the required gateway intents,
invite it to your server/channel, then run `hermes gateway setup` in the selected
Hermes profile. Select Discord, store the bot token locally and configure allowed
users. Run `hermes gateway` and verify a harmless message gets a reply. The gateway
needs the same Jobot skill, checkout/config access and local tools as CLI chats.

Confirmed-submission alerts use a separate optional Jobot observer. Add:

```json
"submission_notifications": {
  "target": "discord:YOUR_CHANNEL_ID",
  "hermes_executable": "/absolute/path/to/hermes",
  "profile_home": "/absolute/path/to/your/hermes-profile"
}
```

Then run `<python> -m job_applier.hermes_notifications --config ABSOLUTE_RUNTIME_JSON once`
to initialize, and use `watch` or the supplied notification service for ongoing
alerts. Tokens stay in Hermes. Outbound alerts use `hermes send` and do not require
a running gateway; conversational replies do. Alerts are not a handler for
answering unresolved application questions—use the dashboard's **Needs your
answer** or the supported active harness flow. See [Submission alerts](jobbot-v1/SUBMISSION_ALERTS.md).

### 8. Verify setup and start using Jobot

These are setup checks, not additional gates on every application:

```text
<python> -m job_applier.application_runtime doctor --config ABSOLUTE_RUNTIME_JSON
<python> -m job_applier.queue_runtime --config ABSOLUTE_RUNTIME_JSON status
<python> -m job_applier.queue_runtime --config ABSOLUTE_RUNTIME_JSON serve
```

Open the configured loopback dashboard (the example uses `http://127.0.0.1:60158`).
Check **Profile** shows you and the registered resume. Check **Settings** for model,
timezone, mode, submission choice, concurrency and application deadline. Setup
defaults to development/review; choose pilot/submit when you intend real submission.
Doctor reports configuration/readiness evidence, not a successful live application.

For the dashboard queue, run this in a second terminal with the same config:

```text
<python> -m job_applier.queue_runtime --config ABSOLUTE_RUNTIME_JSON watch
```

The dashboard server and queue worker are separate processes. After setup, an
explicit application request in Hermes can also use the portable CLI without
either process. Start with your chosen posting and inspect its recorded outcome.
If asked for missing facts, answer in **Needs your answer** and use the retry flow.

For unattended Ubuntu operation, adapt the [systemd templates](../deploy/systemd/)
to your checkout, virtual environment, runtime path, OS user and graphical display.
They include existing-installation paths and are not ready-to-copy universal units.
Keep one queue worker for that installation; see [Operations](OPERATIONS.md).
Discovery is optional and uses `harvest_hermes_command`, the separate harvest skill
and your own search preferences; do not copy another person's leadership filters.

| Symptom | Check |
|---|---|
| Clone says repository not found | The public repository URL is `https://github.com/rejozmathew/jobot.git`; check the URL and network access |
| `runtime_config_not_selected` | Absolute `--config`, process `JOBBOT_CONFIG`, or installed private pointer |
| `job-apply` missing / wrong procedure | Active Hermes profile, `external_dirs`, duplicate skill precedence and full checkout |
| `jobbot` tool missing | Optional native plugin settings/reload; the skill plus CLI is still supported |
| Simplify unavailable | Extension installed and signed in inside the configured retained profile |
| Mail executable found but codes unavailable | Actual account authentication, inbox selection and message delivery |
| Queued job waits | Queue worker, browser availability and Pause/Resume state |
| Discord bot offline | Gateway profile, token, intents and channel/user access |

## Choose the correct entry point

The current application is the managed Jobot runtime. Use the repository virtual
environment and explicitly selected configuration. `run_applier.py serve` starts
the historical dashboard and can show a different database.

| Task | Current entry point |
|---|---|
| Open the dashboard | `python -m job_applier.queue_runtime serve` |
| Run the queue worker | `python -m job_applier.queue_runtime watch` |
| Inspect queue state | `python -m job_applier.queue_runtime status` |
| Start one application from a harness | `python -m job_applier.application_runtime start` |
| Launch/attach the retained browser | `python -m job_applier.workspace_attachment --config …` |
| Read/call managed service operations | `python run_applier.py managed call` |
| Create a new isolated development instance | `python run_applier.py managed init` |

Commands below run from the repository root. On Windows use
`.\.venv\Scripts\python.exe`; on Ubuntu use `./.venv/bin/python`.

## Existing installation

Existing installations already have a candidate, resume asset, history, browser
profile and private runtime configuration. Reuse those records.

Configuration selection is: explicit `--config`, then `JOBBOT_CONFIG`, then the
private pointer at `artifacts/jobbot-v1-private/runtime-config.json`. The pointer
contains `{"config_path":"/absolute/path/to/runtime.json"}`. A pointer is local
installation state, not a file shipped by a fresh checkout.

Windows, with an existing selected pointer:

```powershell
.\.venv\Scripts\python.exe -m job_applier.queue_runtime status
.\.venv\Scripts\python.exe -m job_applier.queue_runtime serve
```

Or explicitly select the existing private runtime:

```powershell
$env:JOBBOT_CONFIG = 'C:\absolute\path\to\existing-runtime.json'
.\.venv\Scripts\python.exe -m job_applier.queue_runtime status
```

Ubuntu:

```bash
export JOBBOT_CONFIG=/absolute/path/to/existing-runtime.json
./.venv/bin/python -m job_applier.queue_runtime status
```

Read the dashboard address from that configuration's `base_url`; `60158` is the
example/default queue-server port, not a discovery mechanism. Open the configured
URL and check the selected instance in **Advanced**, the queue worker state in
**Applications**, and the selected candidate and resume.

The existing Windows private launcher
`python -m artifacts.jobbot-v1-private.runtime_dashboard` may be used where
installed. It is not part of the tracked package. On Ubuntu, use the installed
services rather than starting a second server or dispatcher. See
[Operations](OPERATIONS.md) for read-only status commands.

When the existing browser workspace needs to be opened, its configured launcher
retains its profile and debugging endpoint:

```bash
./.venv/bin/python -m job_applier.workspace_attachment --config /absolute/path/to/existing-runtime.json
```

Leave that browser available while the queue runs. If it was opened without
debugging enabled, use the existing launcher setup described in the
[queue/VM runbook](jobbot-v1/QUEUE_AND_VM_RUNBOOK.md).

## New development checkout

Python 3.11 is the current Windows validation baseline. The pinned managed-worker
dependencies are in [requirements-jobbot-lock.txt](../requirements-jobbot-lock.txt).
Use those for isolated managed-service development. The broader
[requirements.txt](../requirements.txt) includes browser-use and the original
application dependencies; it is not an equivalent reproducible lock file.

Create a virtual environment only if this checkout does not already have one:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-jobbot-lock.txt
```

```bash
python3.11 -m venv .venv
./.venv/bin/python -m pip install -r requirements-jobbot-lock.txt
```

Many managed tests need only the pinned Python environment. Browser fixtures have
additional explicit prerequisites such as Node and an available Chromium-family
browser. The [contributor guide](../CONTRIBUTING.md) explains opt-in validation.
Hermes and Simplify are separately installed integrations, not supplied by this
dependency lock.

### Create a synthetic database and verify the service

This example creates a new **development / review-only** instance. Choose a new
filename; `init` deliberately does not overwrite an existing database. No browser,
employer URL, real candidate or live application is involved.

```powershell
$demoRoot = Join-Path (Get-Location).Path 'artifacts\jobbot-v1-private\docs-demo'
New-Item -ItemType Directory -Force -Path $demoRoot | Out-Null
$demoDb = Join-Path $demoRoot 'managed.db'
.\.venv\Scripts\python.exe run_applier.py managed init --db $demoDb --instance-id docs-demo
$demoJson = @{
    transport = 'local'
    instance_id = 'docs-demo'
    db_path = $demoDb
} | ConvertTo-Json
$demoConfig = Join-Path $demoRoot 'runtime.json'
[IO.File]::WriteAllText($demoConfig, $demoJson, [Text.UTF8Encoding]::new($false))
.\.venv\Scripts\python.exe run_applier.py managed call --config $demoConfig --operation health
```

Expected result: the selected `instance_id`, schema version and review-only
settings. These minimal fields support local service access; they do not provision
a browser, queue executor or dashboard server.

### Provisioning a full runtime

Use [deploy/runtime.ubuntu.example.json](../deploy/runtime.ubuntu.example.json) as
a field reference, replacing every placeholder with the installation's own values.
Provision these pieces explicitly:

1. A managed instance, candidate identity and factual profile.
2. A registered resume asset with a valid local storage reference and SHA-256.
3. Private credential/answer-policy references and, where needed, mailbox access.
4. A configured browser workspace with the official Simplify extension and a
   loopback CDP endpoint; an existing-mode workspace also selects
   `connection_mode: "existing"`.
5. An authenticated external executor and separate discovery configuration if used.
6. Dashboard credentials and a loopback base URL if serving the HTTP UI.

Candidate and document operations are described in [Data model](DATA_MODEL.md)
and [Integrations](INTEGRATIONS.md). Configuration names and their scope are in
[Configuration](CONFIGURATION.md). There is no wizard that creates private
employer accounts, imports production history or supplies authenticated providers.

## First operator walkthrough

For an already provisioned installation:

1. Open **Profile** and verify the intended candidate and resume asset.
2. Check **Settings** for the application model, concurrency and time limit.
3. In **Applications**, check submission mode under application options. Add the
   intended official posting URL. Active intake can be picked up automatically.
4. Select the desired job(s) and use **Queue selected**, or use a row's **Apply now**
   action. Check worker status if the saved request waits.
5. Watch the expanded job or **Activity** for current progress and the final evidence.
6. Answer a required unresolved question in **Needs your answer**, then use its
   ready-to-retry workflow when all necessary answers are available.

[The user guide](USER_GUIDE.md) explains the controls and their side effects.

## Direct harness execution

For a requested application, read the canonical
[job-apply skill](../skills/productivity/job-apply/SKILL.md) and follow its startup
procedure. The shape of the portable command is:

```bash
./.venv/bin/python -m job_applier.application_runtime start \
  'https://employer.example/jobs/role' \
  --config /absolute/path/to/existing-runtime.json \
  --driver-id ACTUAL_CONVERSATION_ID --request-id UNIQUE_REQUEST_ID --wait-seconds 0
```

Replace the placeholders with the requested job and actual conversation/request
identity. Repeated calls for that request retain the same request ID. Local start
performs readiness checks itself; a separate doctor call is optional diagnostics,
not an additional per-application prerequisite.

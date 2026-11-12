# Configuration reference

[Documentation index](README.md) · [Getting started](GETTING_STARTED.md)

## Four kinds of configuration

| Kind | Location | Scope |
|---|---|---|
| Private runtime selection | `--config`, `JOBBOT_CONFIG`, private runtime pointer | Which managed instance and installation this process uses |
| Runtime JSON | Selected private file | Paths, workspaces, executor command, credential/mail references and integrations |
| Operational settings | Versioned records in the selected database | Model selection, mode, concurrency, deadline, discovery and other operator choices |
| Candidate and application data | Candidate, documents, answer library and per-attempt snapshots | Facts, selected assets and approved answers |

The legacy `.env` and root `profile.json` setup belongs to the older application.
The managed runtime does not choose a database from the current working directory.

## Selecting the instance

`application_runtime.resolve_config()` chooses, in order:

1. The explicit `--config` argument.
2. The process's `JOBBOT_CONFIG` environment variable.
3. `artifacts/jobbot-v1-private/runtime-config.json`, containing a `config_path`.

The JSON names an `instance_id` and absolute `db_path`; the runtime verifies that
the database contains that instance. `legacy_history_paths` supplies explicit
read-only success history, not additional write destinations.

For `queue_runtime`, global `--config` precedes the subcommand. For
`application_runtime`, it follows the subcommand:

```text
python -m job_applier.queue_runtime --config /absolute/runtime.json status
python -m job_applier.application_runtime sessions --config /absolute/runtime.json
```

## Runtime JSON fields

The [Ubuntu example](../deploy/runtime.ubuntu.example.json) is a template, not an
installed configuration. Paths, IDs, command syntax and secret references must
match the existing installation. Do not publish a populated runtime JSON.

| Fields | Meaning |
|---|---|
| `transport` | `local` calls service methods in process; `http` uses the optional authenticated API |
| `instance_id`, `db_path` | Explicit authoritative managed instance |
| `identity_id`, `resume_asset_id` | Existing candidate and registered resume used by direct/queued work |
| `spool_dir` | Absolute private location for dispatch files, checkpoints and evidence |
| `base_url` | Dashboard/API address; tracked server is loopback-only |
| `operator_token_env`, `worker_token_env`, `worker_id` | Named HTTP credentials and worker identity; local application start does not need those tokens |
| `worker_tokens_env` | Optional environment/credential-file value containing a JSON token-to-worker mapping for the server |
| `credential_files` | Optional map from a credential name to an explicit private JSON `path` and `key`; environment values take precedence |
| `credential_profile_path` | Explicit private account/credential source |
| `answer_policy_profile_path` | Approved answer preferences projected into candidate data for future attempts |
| `profile_export_path` | Optional absolute private JSON export of the configured `identity_id`'s factual profile; unset by default. Profile Save/import writes it, and the dashboard offers an explicit retry. The parent directory must already exist. It can share the credential profile file; credentials and policy sections are preserved. The managed database remains authoritative. |
| `legacy_history_paths` | Absolute read-only history databases used to suppress recorded successes |
| `workspaces` | Configured browser workspace definitions, described below |
| `hermes_command` | Argument array with a `{prompt_file}` placeholder for an external executor |
| `hermes_desktop` | Optional native desktop-session integration configuration; see its runbook |
| `queue_interval_seconds` | Automatic queue scheduling interval in this installation; distinct from discovery frequency and watcher polling |
| `harvest_hermes_command`, `harvest_instructions` | Separate discovery executor and instructions |
| `mailbox_provider`, `himalaya_*` | Selected mailbox integration references |
| `email_route` | Optional application-recipient versus verification-inbox routing |
| `submission_notifications` | Optional confirmed-submission alert target and Hermes executable/profile |
| `submission_notifications.daily_summary` | Optional `enabled`, local `time` (default `08:00`) and IANA `timezone` (default `America/Chicago`) for the previous calendar day's numerical report; uses the existing Discord target |
| `duplicate_matching` | Optional LM Studio `base_url` ending in `/v1`, embedding `model`, `model_revision` (default `1`) and `title_threshold` (default `0.975`); no secrets or profile data are sent |
| `require_simplify` | Browser readiness setting; current live execution expects official Simplify |

Some older private configurations also contain `concurrency_limit` or legacy
worker budget fields. Current queued capacity is taken from the database's
`application_concurrency` setting, bounded by available managed workspaces where
applicable. Read the current consumer before treating a historical field as active.

### Browser workspace

Each entry uses `id`, absolute `user_data_dir`, absolute `browser_executable`, a
loopback `cdp_url`, and `mode` (`headed` or `headless`). `connection_mode` is
`managed` by default; `existing` attaches to the retained browser. `startup_urls`
can open the local dashboard/mail when that existing browser is launched.

Workspace IDs, profile directories and CDP endpoints must be distinct across
configured workspace entries. Existing-mode concurrency uses multiple application
windows inside one configured retained profile; it does not create duplicate
workspace definitions pointing at the same profile.

The parser supports headless mode. That does not establish that a particular
Simplify installation or employer flow works headlessly.

## Operator settings and defaults

These are code defaults from `managed_settings.py`, not the current values of any
private installation. **Settings** shows effective values and a revision number.
Saving requires the expected revision so one operator cannot silently overwrite
another edit. Application snapshots preserve the choices with which work began.

| Setting | Default | Behavior |
|---|---|---|
| `mode` | `development` | `development` or `pilot`; development uses review-only submission |
| `submission_mode` | `review` | Review-only or `submit` when complete |
| `worker` | `external` | External or Hermes integration |
| `autofill` | `simplify` | Selected autofill strategy; native capability also exists |
| `browser_mode` | `headed` | Requested browser mode |
| `application_concurrency` | `1` | Operator-selectable 1–5 simultaneous queued applications |
| `duplicate_matching_mode` | `shadow` | `off`, show-only `shadow`, or `enforce` high-confidence matches to recorded candidate success or explicit operator cancellation; never suppresses because an earlier attempt failed |
| `application_time_limit_minutes` | `30` | 1–1440 minutes, or `0` for Off; excludes time waiting in queue |
| `reasoning_provider`, `reasoning_model` | unset | Use configured executor selection until an explicit supported selection is saved |
| `reasoning_effort` | `low` | Requested effort; UI adapts to executor/provider capabilities |
| `application_model_override` | `false` | Whether the application model overrides executor defaults |
| `discovery_model_mode`, `learning_model_mode` | `same_application` | Follow the effective application model, or use `separate` |
| `discovery_provider`, `discovery_model` | unset | Explicit provider/model pair required in separate discovery mode |
| `learning_provider`, `learning_model` | unset | Explicit provider/model pair required in separate answer-learning mode |
| `discovery_effort`, `learning_effort` | `low` | Separate-mode reasoning effort; shared mode follows the application selection |
| `discovery_batch_size` | `5` | Up to 1–100 qualifying jobs per discovery run |
| `discovery_interval_hours` | `4` | 1–168 hours between scheduled discovery runs |
| `timezone` | `UTC` | Reporting/calendar timezone |
| `market_countries` | `["US"]` | Operator market preference |
| `excluded_companies` | `[]` | Configured exclusions |
| `screenshots` | `false` | Recording policy setting; execution recovery still follows owned screenshot inspection guidance |

The current default values are defined in source. The model catalog reflects the
installed executor/provider configuration; a model label in static HTML is not
proof that the model is available or selected.

Duplicate matching uses a separate small embedding model, not the application
reasoning model. The model/input hash caches vectors in the selected managed
database. Bump `model_revision` if replacing a model's weights under the same
identifier. Use read-only/shadow assessment before enabling a new model or
threshold; cosine similarity is not a calibrated probability. Missing LM Studio
access does not prevent application work. See
[Cross-source matching](jobbot-v1/CROSS_SOURCE_IDENTITY.md).

Discovery and answer learning read fresh saved settings before each new run/call.
Shared mode resolves the application override first, then the configured application
executor default (Desktop catalog or CLI profile and flags). Discovery still uses
`harvest_hermes_command` for its tools/profile, but replaces conflicting model flags
with the resolved choice. Each run saves requested model metadata in its private
`model-selection.json`; this records routing intent, not proof of successful inference.
Answer learning applies the same choice to synthesis and semantic matching, including
the auxiliary client's main-model recovery context. Legacy `answer_learning` model
values do not override a resolved Settings selection; its launcher remains usable.
Custom external commands retain their own model contract and are not rewritten.
If the Desktop default cannot be resolved, discovery/learning reports the lookup
failure rather than silently using a different profile model. An explicit saved
application selection still works without a catalog lookup; applying is unchanged.

No Qwen model is hardcoded into the managed runtime. An installed Hermes profile,
an explicit separate selection or external executor can still select one. Existing
settings revisions acquire the shared defaults without a database schema migration.
Saved separate choices are retained while shared mode is selected, for later reuse.

Older worker settings include `field_seconds`, `no_progress_seconds`,
`attempt_seconds` and `lease_seconds`. The legacy HTTP worker consumes these
budgets. Local sessions bypass those legacy reasoning budgets and use the
operator's overall application deadline. A 60-second helper call is a resumable
slice, not a one-minute application cutoff.

Global **Pause Jobot**, automatic pickup enablement, queued request identity and
retry due times are durable scheduling state. They are not model settings, and a
server restart does not reset them.

## Privacy and portability

The dashboard's portal password editor uses the runtime's existing
`credential_profile_path`. It adds a private `portal_password_overrides` map to
that JSON file and leaves `accounts.default`, other account entries and unrelated
fields intact. Entries are scoped to candidate ID, verified portal namespace and
account email. Explicit overrides take precedence over the account's saved
credential reference; otherwise the existing reference/default resolution applies.
Removing an override deletes its password and retains only scope/fallback metadata
so a previously recorded override reference can still resolve its prior credential.

This is file-backed storage, **not encryption or a password manager**. The runtime
user needs read/write access to the selected file and its private directory.
Updates use a file lock and atomic replacement; replacement files are owner-only
on POSIX and inherit the private directory's permissions on Windows. Include the
file in private backups, keep it outside Git, and protect the containing directory.
The dashboard API accepts replacement passwords but never returns saved passwords.
Default-password management is unchanged; removing an override whose fallback is
the default uses the currently configured default.

Store credentials in explicit private references or the selected process
environment. Do not put passwords, verification codes or tokens in factual profile
JSON, public docs, queue metadata or example payloads. Upload registration records
the asset hash and local storage reference; the document itself stays private.

Copying a Windows config to Ubuntu does not translate drive paths, executables,
registered asset references or browser profile directories. Migrate deliberately
and preserve the authoritative history. See [Operations](OPERATIONS.md).

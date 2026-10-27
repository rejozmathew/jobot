# Application runtime: ownership, helper map, and rationale

## October 22: harness-independent host dependencies and reset requests

The existing `workspace_host.ensure_host` caller prefers the repository virtualenv
and starts the owned host with Python's `-E` option. A harness can use a different
Python version without its inherited module paths supplying the host's native
dependencies. Existing live hosts, selected configuration, display environment,
session ownership and original application deadlines are preserved. Without a
repository virtualenv the current interpreter remains the fallback.

The shared URL canonicalizer recognizes the connection-name segment on Auth0's
public `/u/reset-password/request/<connection>` screen, including custom database
connections. Ordinary observed navigation proof is still required to adopt it;
the URL alone does not establish application or account ownership. Additional
path segments and secret-bearing query parameters retain the existing treatment.
This removes a false recovery veto before the reset email can be requested.
Neither change adds a helper or caller, changes retry policy, supplies candidate
answers, or establishes employer acceptance.

## October 19: signed form question context

Shared `browser request_answers` / `apply_answers` callers use
`browser_controls.required_questions` and `managed_questions.question_data`.
For otherwise valid embedded-form URLs whose query contains secret-bearing
assignments, question context keeps the document origin/path plus a SHA-256
digest of the complete canonical URL instead of its query values. Different
queries remain distinct; ordinary contexts and existing question keys remain
unchanged. The digest is an opaque context key, never a navigation destination,
account authorization or reusable answer. Query rotation can create another
exact-context question; approved answer-library reuse remains separately scoped.
Public URL validation and secret checks on other question data are unchanged.
Missing facts, current controls, session ownership, deadlines, Simplify order and
accepted submission evidence retain their existing behavior.

## October 17: manual portal password overrides

Accounts & history can set, update and remove a password override for an existing
candidate/portal account. Operator-only `set_portal_password` and
`remove_portal_password` operations resolve the canonical account scope and call
`portal_credentials.update_password`. The selected private credential profile
owns password bytes; no password enters the account ledger, factual profile,
dashboard response or application event. File locking and atomic replacement keep
concurrent fills from reading a partial profile.

The shared private credential resolver reads the scoped override on each fill,
ahead of the saved reference/default. Removal retains non-secret fallback metadata
for previously recorded override references. Both local workspace/Workday callers
and the legacy managed worker use this resolution. The original browser-use
executor remains under `legacy_credentials.py`. No password generation, website
reset, application restriction, retry limit or new execution gate is introduced.

## October 9: retained-browser recovery after startup

`workspace_attachment --watch` keeps the configured retained browser available
throughout the graphical session. The previous one-shot service could remain
`active (exited)` after Brave closed, leaving the independent queue waiting until
the operator reopened it. The service now runs continuously, reusing a live
verified profile and relaunching a missing process every five seconds. Temporary
launch/endpoint failures are retried; existing processes are never terminated to
repair endpoint settings. Manual and supervised launches share a profile launch
lock to avoid duplicate launches. The ordinary manual command remains one-shot.
On Linux, retained-browser lookup prefers the profile's live singleton owner
and otherwise searches main browser processes; leftover renderer/zygote children
do not keep the supervisor waiting after the browser exits. The general managed
profile-in-use check still considers all profile processes.

This adds a supervision caller to the existing browser launcher. Application
hosts still borrow the connection and own only their application targets. Queue
admission, deadlines, concurrency, submission evidence and answer entry retain
their existing behavior. Opening the dashboard is not a scheduling trigger.

## October 8: applied/canceled-posting matching and daily summary

Operator-approved company/title matching supplements observed URL identity.
`job_duplicates.DuplicateMatcher` caches optional LM Studio embeddings outside
database transactions; the shared admission check re-evaluates corroborating
posting facts and candidate-specific success or explicit operator cancellation.
`matching_suppression` reads the original disposition at admission; restoring
the original or dismissing an incorrect pair removes cancellation exclusion.
Only `enforce` mode skips new
admission; shadow results and failed/uncertain attempts remain eligible.
Original jobs, attempts, outcomes and browser-scope aliases remain unchanged.
See [Cross-source identity](CROSS_SOURCE_IDENTITY.md) for evidence requirements,
cache invalidation, operator dismissal and reporting semantics.

The existing notification watcher can send one report per completed calendar
day at 08:00 America/Chicago. It records daily delivery receipts independently
of application history and keeps normal retries unchanged. See
[Submission alerts](SUBMISSION_ALERTS.md#daily-numerical-summary).

## October 7: desktop startup preserves queued requests

`queue_runtime.dispatch_startup` observes the Hermes desktop backend and a usable
configured retained browser before `queue_take` reserves a request. The backend
probe uses the existing authenticated loopback connection and a read-only
`session.active_list` RPC with short timeouts. Browser checks reuse profile/process
and CDP verification. An unavailable dependency returns a worker startup-wait
state; the watcher keeps its heartbeat, wake request and due check while leaving
request identity, retries and application deadlines untouched. Active dispatch
supervision still runs first, and custom executor/managed-browser paths remain.
The dashboard displays the specific dependency being awaited.

The optional `jobbot-browser.service` starts retained-browser supervision
at graphical login (continuous recovery was added October 9). Its queue drop-in orders service startup without replacing
the existing Hermes desktop autostart. It reuses an already-open configured
browser, and is independent of queue-service restarts. No ATS helper, candidate
data, submission policy, retry count or memory allocation is changed.

## October 7: popup observation for page-only helper callers

The shared popup document observer uses the already-armed loopback endpoint and
correlated child target when a helper owns a page without borrowing the browser
wrapper. The iCIMS Apply and authentication-Continue callers use that contract.
Previously a newly correlated popup could raise NoneType.base_url before its
first document was observed, returning otherwise supported navigation to the
executor as an exception.

The original observation window, public destination/identity checks and ordinary
same-session recovery are retained. Normal browser callers keep their observed
browser mode. No helper or caller is added or removed, and there is no change to
Simplify order, confirmation sources, operator stops, deadlines or retry policy.
This correction does not reconcile an unrelated posting incorrectly adopted
during authentication; that separate identity finding remains under investigation.

## October 6: company templates and visible answer reuse

The existing shared `managed_answer_library.matches` resolver binds `{company}`
in learned questions/aliases to the posting company. Global defaults retain the
existing company/job exception precedence, choice mapping and conditions. Semantic
wording learning retains company slots for existing templates and runs between
synthesis units so a history backlog cannot starve pending question matching.
Existing learned sentences with an explicit leading Yes/No map to Boolean controls
after full-label matching; text controls keep the complete response.
Synthesis retains direct Yes/No answers for choice mapping and distinguishes
explicit cross-employer defaults from facts about just one employer.

`AnswerLibraryServices.answer_library` now projects matched-question and recorded
form-use evidence from response history and existing private answer journals.
It shows counts, recent applications, answer revisions and last use. Context-only
reads omit this projection; journal parsing is cached by file timestamp/size.
The existing journal writer retains changes in answer provenance even when the
selected answer stays the same. The executor brief and canonical skill explain
company templates, standing recovery authorization and form-journal attribution.
No helper or caller is added or removed; submission evidence policy is unchanged.

Start with the [architecture guide](../ARCHITECTURE.md) for a component overview,
the [user guide](../USER_GUIDE.md) for dashboard behavior, and
[configuration](../CONFIGURATION.md) for current setting scope. This detailed
reference retains the canonical helper map and dated implementation rationale.

## October 4: contention recovery and compact projections

`Service.read` opens a read-only, deferred SQLite snapshot; reviewed dashboard,
session, history, settings and queue projections use it without reserving the
writer. `Service.tx` retains immediate write transactions and records slow waits
and contention without SQL or private values. Migration 28 adds non-unique
attempt/session/dispatch lookup indexes and observed posting aliases. Session
history is projected from a single batched snapshot, and visible dashboards poll
every five seconds; hidden dashboards wait until visible again.

The queue watcher and workspace monitor retain owned work after SQLite BUSY or
LOCKED. Queue preparation resumes the same reservation, and launched executors
are retained before their process identity is persisted. Cached deadlines run
before fallible bookkeeping. Browser preparation reclaims its owned unfinished
targets before retrying readiness. These paths neither replay application actions
nor reset the operator's deadline. Other database errors remain visible.

Existing shared navigation recognizes LinkedIn notification posting URLs, observed
public password-reset request routes, explicit embedded posting links and observed
assessment invitations. Current navigation correlation, account selection and job
conflict checks still apply. Verified employer posting aliases feed intake, retry
context and distinct-posting reporting without rewriting original job/attempt rows.
Reporting separates affirmative already-applied evidence from new submissions and
also exposes recorded counts. Retry context retains the latest actual obstacle
and current saved question answers when later host interruptions obscure them.

`browser_controls.inventory` retains observed controls, answer facts, policies,
recovery operations and verification details while referring to its existing
structured recovery guidance instead of repeating it. No helper or caller is
added or removed, and no application restriction, approval gate or retry limit
is introduced.

## October 3: preserve observed application routes through authentication

The shared navigation helper used by ordinary browser actions and iCIMS continues
to correlate Apply and authentication navigation from the owned document. An
unknown-stage form containing email/password and only choice controls can now
retain that authentication navigation evidence as well. A privacy dropdown no
longer hides the email-to-password continuation. This does not relabel the form,
select consent, change Simplify order or add navigation waits to ordinary profile
forms with text fields. Credentials still use the selected employer account.

After a successful ownership/writer observation, the workspace host refreshes
application context before credential entry because that observation can promote a
delayed route. The private filler retains its own current-route and candidate
checks. The observer also accepts existing child routes of an already-verified
canonical application target, even when its path differs from the intake path.
No static host/site alias is inferred; an unobserved route, different requisition,
different site/host or conflicting query remains outside that retained scope.

The shared browser observer uses the same ownership-checked full application
route as the other managed helpers. An owned target's display URL omits its query
and must not replace that verified route during identity checks. This preserves
child-form continuity after a same-origin canonical redirect, including observed
tracking parameters, without accepting a different job, site, host or query.

These are updates to existing shared navigation, observation and credential
callers; no helper, executor, retry limit or application-time gate is added. Daily
engineering reviews use the counterfactual and baseline/candidate replay workflow
in [SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md), including successful controls and
capacity effects, without treating historical accounting as regression proof.

## October 3: AI learns generalized knowledge from application responses

The inbox's primary **Save answer** action records human responses for the selected
applications using `answer_questions`. **Add reusable answer** is a separate optional
manual action. Saving a response does not create an exact-copy library entry or wait
for inference. Fully answered applications use the existing retry flow.

Migration 27 adds response-learning work records and an origin label on current
knowledge. The dashboard's independent `AnswerLearner` thread synthesizes reusable,
general questions and grounded first-person answers through the installed Hermes
auxiliary client and its authenticated provider configuration. It runs no application
executor, tools, browser or application session, and never holds a database transaction
while waiting for a model. Learning failures retry independently; human responses,
application progress, dispatch policy and browser recovery remain available.

Original questions, answers, company/position context and version history remain
inspectable. Existing raw library entries retain their IDs and immutable earlier
versions while AI generalizes them. Already-general questions can retain their wording.
A raw legacy copy that cannot be extracted or conflicts with current knowledge moves
to Retired, preserving full responses for active applications.
Explicitly restoring that archived copy labels it as manual knowledge. The model
must not invent generic candidate facts. Company/job scope and currency, pay period,
country and time qualifiers are retained. Exact source quotations substantiate each
extraction. New facts conflicting with current knowledge appear for review, and
concurrent edits win over model results. AI-derived entries edited by the user remain
labelled as such; manual entries are labelled **Added by you**.

That same synthesis call also compares the proposed answer's meaning with the
selected existing entry. Equivalent wording can merge with exact quotations from
the existing answer and identical scope/conditions; text equality remains supported.
The service rejects obvious polarity, quantity, currency and pay-period differences
from this merge, and uncertain comparisons remain conflicts. The merge preserves
the existing answer, question and origin while adding provenance and eligible
aliases with optimistic revision checks. This does not change application execution
or create an additional model call.

A second auxiliary pass compares pending questions with current knowledge and adds
only equivalent question wording. Reconciliation still maps current answers to the
actual form choices and checks scope/conditions. A generalized career motivation
cannot automatically stand in for an incomplete compound employer-specific response.
Unchanged misses are cached; changes to current knowledge permit another review.
The application executor receives the generic knowledge in its existing context.
The Learned answers tab separates current knowledge from learning activity and
shows the original source responses. Closed application responses feed learning
without returning to the actionable inbox. A supplementary company pass can extract
company knowledge from original responses, including system-archived raw copies,
without restoring those copies. Company-scoped knowledge remains available across
roles at the same company; role-specific details stay with their application.
Current edits and explicit retirement take precedence over older source history.

## October 2: current reusable answers and an actionable inbox

Migration 26 adds an operator-owned Answer library in the authoritative database.
Entries are candidate-scoped, versioned and editable, with global, company or
application scope, accepted question aliases and optional country/currency/pay
period context. Known narrow wording variants share an intent; negation,
sponsorship now versus future, currency symbols and offered option meanings are
retained. Company scope uses the company the operator selects, not a shared ATS
hostname. More specific entries take precedence. Conflicting applicable entries
are exposed for operator repair rather than resolved by frequency or age.

Existing profile facts remain a source: saving/importing a profile and saving,
editing or retiring library knowledge reevaluate outstanding questions. Profile
facts do not get copied into another permanent library record. Explicit human
answers for one application remain overrides. Submitted/canceled/archived
requests keep their snapshots; they are not rewritten by reconciliation. Every
library revision and derived response revision is append-only. Retiring a library
entry preserves history and removes its current reuse; an old journal cannot
silently restore it. Ordinary executor facts, interpretation and control recovery
remain available when a library match is absent or unsuitable. This introduces no
application deadline, retry limit, finish condition or additional approval gate.

`application_context` supplies current entries without their full edit history.
Shared `saved_answer` supplies Greenhouse, iCIMS and LinkedIn residual handling;
Workday receives the same library in its screen context and can use shared
`request_answers` / `apply_answers`. Those operations resolve current knowledge
against freshly observed choices before asking a person. Private response journals
retain the selected library ID/revision as provenance. Simplify order, browser
ownership, writer checks and submission evidence remain unchanged.

The dashboard groups repeated outstanding requests and can save one scoped answer
for them. Learned answers has its own top-level navigation entry. The inbox,
ready applications, history and learned answers use paginated 12-row views.
The inbox defaults to bulk editing with one Save drafts action; Focus on one question
opens the individual detail pane. Company and position are visible before answering;
question selection and drafts survive polling and list reordering. Focused mode
uses a question/application picker on mobile. Save receipts link to AI learning activity,
and a resolved question advances to the next request without losing other drafts.
Learning records include the companies and positions they came from.
These views separate action from records. Submitted, canceled, archived and
explicitly queued answer retries leave the inbox without asserting that an unanswered question was
answered. History is searchable and paginated, including response revisions.
Human response history supplies background synthesis inputs; conflicting facts require
review before replacing current editable knowledge.
The existing dispatcher reevaluates current knowledge once per minute, including
while automation is paused; it performs no browser work or model calls. Existing
queue policy still controls whether and when an answered application retries.

## October 2: concurrent application windows in the retained browser

Settings `application_concurrency` selects 1–5 simultaneous queued applications,
defaulting to 1. The selected model/provider remains a per-dispatch snapshot;
operators can choose 1 for a local model and raise the count for another executor.
Reducing the count drains existing attempts normally before refilling slots.
Pause Jobot stops new admissions while supervision and cleanup continue for all
running attempts. Each retains its own original application deadline and evidence.

`queue_runtime.watch` launches without waiting for an executor, retains/reaps each
child, and reconciles every dispatch on each pass. A live executor no longer hides
another executor's completion or deadline. `managed_queue.queue_take` checks the
operator's capacity atomically. Private briefs, model sessions, deadline clocks
and receipts remain per dispatch. Capacity accounts for independent manual sessions
and browser cleanup, and preserves the existing manual-request/retry ordering.

Migration 25 replaces the one-session-per-workspace index with a lookup index.
`managed_sessions.reserve_session` counts applications and allows an existing-mode
workspace to host several owned tabs. Managed-process workspaces retain exclusive
allocation. No profiles are created, copied or cleared for concurrency. The
existing Jobot browser retains cookies, extension setup, history and personal tabs.

`workspace_host` retains one profile lock and supervises every session in that
browser. Separate request connections and per-session operation locks allow
target-scoped helpers to progress concurrently; calls within one application still
serialize. Startup attachment work is serialized. Each application opens a normal
window in the same profile, with its own selected tab. The installed Simplify 3.1.8
field filler waits for `visibilitychange` when the document is hidden; briefly
foregrounding a background tab for a click is insufficient for an entire fill.
`prepare_target` records the created window ID in the durable browser attachment,
then `arrange_application_windows` tiles only active application windows within
the screen's available area. Personal windows are not resized, and a tab moved
to a different window does not transfer window ownership. Layout and input share
the short input lock, preventing a resize midway through a trusted click. Layout
failure remains diagnostic and does not end or prohibit application recovery.
`CDPPage.input_turn` briefly foregrounds the owned tab and serializes
trusted pointer/key input across that browser. Embedded-frame clicks use the same
root-page turn. Focus emulation is enabled only for that turn and disabled afterward
so occluded desktop pages receive trusted input as well. This prevents acknowledged background clicks from losing popup
activation; model reasoning, DOM work and page waits remain concurrent. Stop,
finish, restart and deadline cleanup close only that application's
durably owned targets/popups. An expired shared-browser application does not retire
the host of other active applications. Host-crash recovery visits all retained
sessions. Existing target, driver, writer and submission ownership checks remain.

Preparation rechecks the durable session state under its operation lock before
creating a window, so an old monitor snapshot cannot reopen a connected attempt.
Attachment refreshes retain all owned target IDs within the same browser
incarnation. Terminal cleanup therefore closes earlier pages and their popups for
failed, blocked, successful and interrupted attempts before releasing capacity.
Target history does not transfer to a replacement browser incarnation.

Tests use synthetic databases and localhost forms with disposable profiles. They
exercise atomic capacity, queue refill/pause, settings, target ownership, concurrent
input, retained cookies, popup cleanup and same-attempt restart/host recovery.
The real-browser fixtures run at 3 and 5 windows and include delayed field fills
that wait while hidden, matching the installed extension's visibility behavior.
These fixtures do not establish live ATS acceptance or the official Simplify
extension's behavior during simultaneous autofill. Shared employer login state
continues to be shared across tabs, as it is during ordinary manual browsing.

## October 2: recovery continuity

`workspace_host` persists an owned restart as `preparing` before requesting tab
closure. Delayed closure and reopening errors remain resumable preparation;
ordinary supervision retries while the saved deadline and operator control allow
it. Verified closure releases writer state, then the same session/attempt reopens.
A host restart can resume that durable state. Status exposes the recovery phase
and latest error. Submission evidence and the original deadline survive.

`managed_runtime.browser_observe` can settle a prior unknown writer when stable
receipts explicitly show that every accepted document is a nonparticipant, with
no pending activity, unresolved frames or unfinished managed action. Unknown
participation and actual pending writers still need their existing settlement.

The shared `application_runtime.click_and_follow_external_apply` also observes
Next/Continue/sign-in navigation from an inspected authentication stage. Its
callers are shared browser ref/selector activation and iCIMS entry/continuation.
The existing navigation trace and handoff checks establish the current route;
`managed_sessions.application_job` retains the verified employer account URL for
account namespace selection across this authentication transition. Intake URLs
remain unchanged. Unobserved login navigation does not establish ownership.

## September 28: delayed same-origin form navigation

`managed_runtime.browser_observe` uses `route_history.reconcile_history` before
its identity observations. It retains the verified main-document CDP history
entry ID and source URL with the local session, attempt, fence, target and browser
binding. This evidence survives a helper connection closing before Next finishes,
including same-entry `replaceState`. A fresh history/current-URL pair can project
an observed same-origin continuation through the existing `handoff_target` checks.
History is not treated as a network redirect chain or a general domain allowance.
The full traversed segment is compared with the original application identity as
well as the latest source. Anchor comparison and route promotion are atomic.

Writer settlement, selected autofill strategy, saved deadline, account principal
and submission evidence retain their existing responsibilities. Missing history
leaves ordinary recovery available. Cross-host Apply correlation remains in its
existing helper; observed authentication continuity is described above.
The iCIMS runner refreshes the projected context before reading an embedded form
after an observed route change, including within the same helper call.
Its posting Apply path also uses `application_runtime.click_and_follow_external_apply`
before activating the observed control, retaining the existing same-tab/popup
correlation. A popup returns a resumable snapshot handoff so the next call connects
to the newly owned target; same-tab adoption refreshes context and continues.
The refreshed package also refreshes derived profile/email facts. A fresh inspection
that identifies final submission updates the local decision and audit before
Autofill or the existing review/submission service handles that control.

## September 27: operator pause for a break

Migration 24 retains `dispatch_control.automation_paused` independently of the
automatic pickup setting. The dashboard header and queue CLI send `pause_all` /
`resume_all` through the existing operator `queue_control`. `queue_take` and
`harvest_runtime.run_harvest` check it in the same transaction that admits work.
Admitted application/discovery work finishes normally; queue recovery and cleanup
continue. Pending manual requests and retry due times survive the pause. The
discovery timer treats a paused check as a successful no-op. Resume restores
normal scheduling without changing prior settings or submission evidence.
This is the operator-requested queue/discovery control; it adds no failure-based
restriction, automatic retry limit or rule for independent manual sessions.

## September 27: route continuity and retry learning

`cdp_client.NavigationTrace` observes the owned main document before startup or
an Apply action. `workspace_host.prepare_target` and
`application_runtime.click_and_follow_external_apply` pass observed navigation
to `managed_sessions.handoff_target`. Public redirect chains retain the original
posting and reject conflicting known requisitions. Popup selection still requires
its exact expected destination; a different popup is never inferred from its opener.
After that correlation, `cdp_client.observe_popup_document`, called by the shared
Apply helper, follows the same target through its first document commit using
the remainder of the existing five-second observation window. An observed public
redirect becomes the handoff route through the existing identity checks. A ready
document adds no fixed wait; same-tab and ordinary field actions do not call it.
Slow, disconnected, private or conflicting destinations retain the original
handoff for executor recovery. The application deadline is unchanged. This does
not establish ownership for emailed private reset links or unrelated popups.
Greenhouse API posting URLs start at the matching hosted application form.

`managed_sessions.application_job` projects the verified current route from the
owned target. Context, target rebinding, account events/mail and account coordination
use that projection. `browser_frames.router_for` refreshes an existing reader's
package while retaining frame ownership/document checks. Intake and historical
posting URLs remain unchanged.

`managed_context.prior_application_history` supplies bounded, deterministic prior
outcomes and recovery evidence to the execution brief and context for the same
candidate and related posting. History is advisory. `application_answers.reusable_answers`
feeds the Greenhouse and iCIMS runners only verified exact-question answers with
matching profile/candidate/posting provenance; fresh refs and current option checks
still govern writes. Unverified observations, passwords and verification codes are
not reused. Original saved human-answer handling remains in place.

The shared account ledger distinguishes explicit `account_absent` and
`creation_rejected` outcomes from an uncertain creation click. Workday observes
those signals inside its current authentication form. It records explicit rejection
before handing off field/credential repair and does not replay unchanged rejection.
Generic invalid credentials do not establish account absence.

`hermes_desktop` reconciles native idle state with the owned managed application.
An unfinished application can continue in the same native conversation with the
original deadline. User controls, input waits, ownership transfers and actual
outcomes remain authoritative. Explicit RPC rejection differs from a lost reply;
uncertain prompt acceptance uses a unique visible marker and private native history
inspection, never a second blind submission. Compact native failure signatures
remain separate from cleanup. Due automatic retries follow ready fresh/operator
work; existing retry due times, limits and eligibility remain unchanged.

Daily iteration procedure: [Self-improvement](SELF_IMPROVEMENT.md).

## September 21: Greenhouse forwarded verification

Private runtime configuration may set `email_routes.greenhouse` with
`application_email` and `verification_mailbox`. The former overrides only the
Greenhouse form contact email; the latter describes where the existing mailbox
integration reads forwarded verification. No personal-inbox credentials are
requested, changed or inferred from the form address. Forwarding must be set up
at the mail provider; this configuration does not claim delivery is verified.

This is an optional workaround isolated in `email_routing.py`. To disable it,
set `email_routes.greenhouse.enabled` to `false` or remove that entry from the
selected private runtime configuration, then reload the affected runtime services
at an idle boundary. New attempts use their ordinary candidate email and mailbox
handoff. Existing attempts keep their frozen route. No migration or candidate,
account, credential or history rewrite is involved. For source rollback, revert
the dedicated email-routing commit as a unit; the unused private config key may
then be removed independently. A new connected inbox can use the normal candidate
and mailbox configuration after this workaround is disabled.

`application_runtime.start` freezes the route in session credential metadata.
`managed_context` exposes the effective Greenhouse email in a copied context
profile while retaining the original candidate and attempt records.
`application_brief`, runtime handles/snapshots and `managed_credentials` expose
the route through `hermes_gmail.mailbox_handoff`; it supplies routing guidance,
not another mailbox verifier. `greenhouse_fast` handles recognized employer-hosted
forms as well, restores the approved email after Simplify/refill ahead of saved
answers, and returns the existing jobs-inbox handoff on verification. Other ATS
profiles and integrations are unchanged. The canonical skills explain forwarded
recipient correlation and that different addresses do not establish a blocker.

## September 20: Greenhouse missing-email continuation

`greenhouse_advance` accepts `recovery:"missing_verification_email"` after the
executor's documented recipient/mailbox and 1–2 minute delivery checks. The
trigger is Greenhouse-only and requires a current incomplete verification group;
the flag reports the executor's observation that the requested email is absent.
Other ATS email flows do not acquire a timed reload policy. The
existing native/portable caller and workspace host still resolve the owned target.
On a custom parent page, the helper uses its existing ownership-checked frame
discovery to identify the Greenhouse application before routing this recovery.
An unknown parent hostname alone does not reject an accepted embedded form.
Current verification evidence still determines whether a reload is needed;
an ordinary form resumes without reloading, and unrelated ATS routing is retained.
`greenhouse_fast.advance` calls shared `application_runtime.browser_action` reload,
then reconnects to the fresh document and runs its normal Simplify/residual/submit
path within the remaining call slice. The existing runtime keeps the overall
application deadline. A later ordinary advance resumes without another reload.
Verification handoffs include that concrete recovery operation; a renewed employer
verification requirement remains incomplete, never inferred success. Approved
journal answers are rebound with fresh refs; supplied old-ref plans are discarded
on explicit reload. No new retry limit, finish gate or automatic challenge bypass
is introduced. The question schema retains actual country menus exceeding 200
choices instead of rejecting the entire residual batch on the old size cap.

Synthetic coverage in `test_greenhouse_email_recovery.py` exercises owned reload,
refill, actual confirmation versus renewed verification, and large choice sets.

## September 19: form continuity and application deadline

`application_deadline.py` freezes the Settings `application_time_limit_minutes`
at dispatch (default 30, zero means Off). `queue_runtime` enforces it independently
of model output and restores it from the private dispatch config after a restart.
`hermes_desktop` uses the installed `session.interrupt` API for the exact native
task and confirms idle state; it never terminates the shared model server.
`workspace_host.remember_native_driver` calls `hermes_desktop.remember_driver`
in the background to retain the stable native task ID across chat compression.
That ID is paired with the current driver and refreshed after an explicit attach.
`workspace_host` reads the same durable budget from session metadata, refuses
further actions after expiry and performs owned-target cleanup outside a stuck
helper lock. Manual starts freeze their own budget; same-request recovery retains
it. The queue waits for cancellation and browser cleanup acknowledgements. A
temporarily unreachable backend remains cancellation pending, not falsely stopped.
The original submission evidence and ordinary retry schedule remain authoritative.
Settings edits affect future requests, not active attempts. The legacy
`attempt_seconds` field belongs to the old leased-worker interface and is not
this local application deadline. The dashboard provides a dedicated time-limit
control and shows each recorded session's deadline.

`managed_sessions.handoff_target` retains the existing Ubuntu Apply popup/same-tab
implementation and records observed same-tab continuation from a verified owned
document. Explicit requisition IDs can match posting paths to registration query
parameters; an ID-free intermediate requires observed owned navigation. The
initial employer identity remains available to detect a later conflicting job.
`managed_runtime.browser_observe` gives `next_operation` the same identity and
writer decision used by execution, and distinguishes current, assigned and
application URLs. Query redaction does not remove internal identity evidence.
Workday dispatch can use an accepted employer handoff instead of only the intake URL.

`browser_controls.inventory` retains read-only fields during route recovery and
returns missing/invalid required controls, exact action shapes and approved contact
facts. The shared form reader recognizes native, ARIA, label-asterisk and required
validator evidence, including a nearby unassociated label for a unique field.
`application_runtime.browser` method `repair` calls `browser_controls.repair_fields`
to group existing fill/select/check actions in one connection, checking document,
writer and ownership state between operations. Upload remains the existing
selected-asset operation. Browser navigation, shared form observations, answer
history and Workday/Greenhouse callers retain their original responsibilities.
Previous-attempt summaries were added in the September 27 iteration above.

Validation and deployment evidence: [September 19 repair](FORM_REPAIR_20260919.md).

Settings model selection: `managed_settings.SettingsServices.model_catalog` exposes
an operator-only, read-only catalog through `model_settings.model_catalog`, using
the configured Hermes Desktop profile's `model.options` RPC. Only provider/model
identifiers, labels and reasoning capability are returned; credentials and endpoint
URLs stay with Hermes. `queue_runtime.dispatch_one` reads the latest settings once
through `model_settings.application_selection` and freezes that choice in the
dispatch's private runtime file. `hermes_desktop.run_session` passes it to
`session.create`; the Hermes CLI path uses explicit provider/model/reasoning flags.
No running conversation or global Hermes profile is changed. Existing installations
inherit their executor default until an operator explicitly saves a model override.
Custom external commands retain their own model configuration; legacy worker
requests still use the existing settings/capability matching contract.

`model_settings.task_selection` also resolves discovery and answer-learning choices
from fresh settings. Both default to `same_application`; `separate` uses an explicit
provider/model/effort pair. `harvest_runtime.run_harvest` resolves before stripping
Desktop routing, keeps the discovery CLI profile, replaces stale CLI model flags,
and records a private immutable `model-selection.json`. `AnswerLearningServices`
calls the same resolver for synthesis and matching. `answer_learning_model` supplies
the selected authenticated runtime as the auxiliary client's main-model context so
recovery does not inherit an unrelated profile default. Existing attempts are not
changed and no application-execution gate is introduced. See the current model
inventory in [Integrations](../INTEGRATIONS.md#model-call-inventory).

The canonical job-apply prompt also carries the user's approved earliest-start
fallback: calculate 14 calendar days from the current date when no more specific
approved availability exists, formatted for the employer's date control.

September 18 throughput repair: the existing navigator bridge can enrich missing
routes through `integrations/jobnavigator_bridge/resolve_routes.py`. This is an
intake helper, not an application executor. It observes only a newly created
background target in the existing signed-in browser, yields to application work,
and closes its own target. Confirmed routes update the same JobNavigator source
row through its authenticated API; the existing bridge remains the intake/queue
writer. Its legacy identity compatibility preserves receipt keys. See the
integration README for installed callers and the user timer.

Discovery now instructs the executor to publish each verified checkpoint through
the existing idempotent intake command. A later model failure can leave an
incomplete discovery report without discarding already published jobs. Greenhouse
API board/requisition evidence accompanies alternate employer URLs. Application
briefs name the LinkedIn and Greenhouse helpers, describe compact checkpoints,
and provide the CLI fallback for an older in-memory native plugin schema.

This is the authoritative local-session architecture, implemented on Windows in
September 2026. Older HTTP accept/claim/lease startup is **compatibility only**.
Historical failures in REVIEW_HANDOFF remain historical evidence. Actual delivery
checks and unresolved acceptance are in [RUNTIME_SIMPLIFICATION_LOG.md](RUNTIME_SIMPLIFICATION_LOG.md).

The current cross-portal request and retry contract is in
[RETRY_POLICY.md](RETRY_POLICY.md). A new request matches the existing job and
starts a fresh attempt unless successful submission is recorded. Failed,
interrupted and submission-unknown history remain intact and do not prevent
another attempt. Actual browser cleanup is a separate lifecycle responsibility.
This September 9 follow-up supersedes earlier uncertainty and same-job/account exclusion guards;
the previous 761-test checkpoint does not validate this later change.

The [first-principles stop-condition audit](STOP_CONDITION_AUDIT.md) challenges
the necessity and placement of the restrictions described here. It distinguishes
current behavior from proposed simplification and includes a source catalog and
read-only historical incidence, followed by the implemented changes and validation.

The existing runner connects native/extension observations to mapped recovery.
Per-application outcomes and detailed diagnoses are retained in the managed
database and existing attempt reports. The proposed additional Workday
authentication recovery remains unimplemented. Design rationale and prioritization
are in the implementation log; describing an implementation here does not
establish live acceptance on every ATS.

Helpers support executor reasoning across all ATSs. A helper `blocked`,
`inspection_required`, unsupported control or call-budget result does not close
the application or establish its outcome. The executor inspects the supplied
controls/options and evidence, tries a different supported interaction and
resumes progress in the owned session. Recovery timing belongs in the existing
timeline so slow cases can guide later engineering. An actual unresolved
obstacle, user stop, or submission evidence determines the eventual outcome;
a helper's matching limits do not. Shared browser/Simplify responses and the
canonical job-apply skill carry this instruction to the executor.

Missing expected controls now trigger visual recovery explicitly. Shared browser
snapshots automatically attach a masked private screenshot when no enabled native
or Simplify progress control is found, structured/frame inspection fails, or the
owned page's identity is unresolved. The result instructs the executor to read the image with
its harness image tool, inspect frames/overlays/inner scrollbars, and continue.
Capturing without inspecting is insufficient. Screenshot failure remains a
recovery diagnostic, not another finish gate. The same instruction is exposed
in the common screen recovery payload, including Workday, and in canonical skills:
inspect a fresh screenshot and remaining plausible actions before giving up.

iCIMS was already detected by hostname, but previously used the generic exact-path
matcher. Its `/jobs/<numeric-id>/.../job`, `/login` and embedded-view URLs now
compare by scheme, employer host and job id. Slugs and page-mode query parameters
do not change the job. The existing frame router, browser/credential write paths,
target binding and URL comparisons reuse that identity. Stored URL hashes and
history are not rewritten. Start/status includes `platform` and `ats_reference`
while preparing. The iCIMS reference describes the observed posting-to-Email/Next
flow without assuming later stages. iCIMS first inspects the posting/frame and
opens the observed Apply control before using Autofill on application details.

Workday's empty recruiting-source prompt has a scoped fallback after Simplify
settles. It preserves existing answers, follows parent categories to leaves,
uses native pointer selection and scrolls only the associated virtualized popup.
Named source preferences fall back to any other offered source as authorized by
the user. It retries stale/uncommitted choices and returns actual alternatives
plus the attempted path when executor judgment is needed. The existing
`fast_forward` recovery mapping accepts `screen_key` and `source_choice` to
continue with an executor-selected label. Native application entry prefers
Apply Manually and other direct Apply controls over chat. These changes are
included in the September 9 checkpoint. Attempt 44 exercised the flow and
submitted with user intervention; its remaining issues motivated the follow-up
changes below. The checkpoint's subsequent regression results are recorded below.

Every portal uses application entry/authentication first, then available Simplify
Autofill, then residual helpers, then executor field-by-field and screenshot
recovery. Initial Autofill precedes Continue even when a stale Complete or
needs_review label is visible. Shared document/step receipts survive reconnects
and field edits; conditional form expansion does not automatically refill over
manual repairs. Accepted iframe controls retain their frame-qualified refs,
and a parent panel follows embedded logical form steps. Workday and Greenhouse
retain their specialized receipts and writer/ownership rules. A mistaken reference to Workday's Autofill
panel tab can resolve to the unique observed Autofill This Page action in the
same document. The shared screen handoff exposes approved standard answers on
every ATS. Workday also exposes the full field question behind Select One and
requests executor completion instead of returning a bare blocked result.
Source repair runs only after advancement cannot proceed; it never intercepts
an already selected Continue action. Workday selection metadata includes chips,
including suffixed IDs and chips inside an expanded prompt, instead of treating
an empty search input as an empty answer. Generic select/combobox inventory also
reports selected values. Shared native field/answer/upload requests use available
initial Autofill first and report that the requested field action has not run.
Workday mapped non-authentication recovery also returns fresh refs after filling.
Small email/password access forms are distinguished from full profiles containing
those same controls. A form's Apply submit button uses the submission service;
posting-entry Apply precedes footer-field repair. Missing or unsupported Simplify
continues through supported helper/executor recovery, respecting native-only settings.
Choosing answers remains executor reasoning governed by the common job-apply
skill, not arbitrary yes/no generation. The human queue is invoked
only explicitly and still reuses policy/exact saved answers. These changes are
included in the requested local checkpoint; the final follow-up changes still
need live validation.

Page recovery is shared across every ATS. `browser` method `reload` deliberately
cancels the current document, so an unknown Simplify writer cannot deadlock the
refresh needed to recover it. The host queues tool calls on the physical browser; historical submission
uncertainty does not prevent recovery. CDP verifies a new document before clearing
the old writer state; subsequent observations govern new form writes. The host's
`restart` operation reuses pause/attach to stop the owned process tree and reopen
the assigned job with the same profile, session and attempt. Shared screen and
Simplify/startup handoffs expose these operations for broken pages and missing
Simplify on Workday, iCIMS, Greenhouse and proprietary sites. Executor judgment
selects further recovery; missing controls are not an application outcome.
Workday additionally recognizes its explicit Something went wrong / refresh
message and attempts one automatic reload. Shared `wait_for_page_recovery` then
observes usable native/extension controls before returning success; document
replacement alone is not application readiness. A transient missing panel returns
loading/waiting instead of a new failure. Fresh recovery responses say to continue
once the old error is gone, not refresh/restart again. New documents reset Workday
page fill receipts; rerenders do not.

The user confirmed attempt 44 submitted successfully, with employer confirmation
and 710.9 seconds recorded, but needed intervention. Its retained logs show the
executor repeated reload and restarted after the original error cleared, source
repair intercepted an enabled Continue despite a selected chip, and manual work
continued on Self Identify until the user requested Autofill. The changes above
address those observed decisions; their new behavior is awaiting live validation.

Startup instructions launch immediately after the canonical skill using
`wait_seconds:0`, overlapping host preparation with ATS-skill reading. They no
longer place ATS reading before browser startup. Optional doctor/repeated config
checks are not startup prerequisites. Metadata records runtime entry/preflight
duration plus host browser-launch, endpoint-ready and employer-navigation times.
These distinguish runtime delay from executor time before the start call; the
runtime cannot measure prompt-to-tool latency on its own. For historical attempt
43, reservation to connected was 8.85 seconds; earlier executor/preflight time
was not captured. The user requested a local checkpoint before Greenhouse work.
Python/JavaScript syntax and diff checks passed. Regression was initially deferred
under the user's prior instruction, then authorized and completed through
Antigravity/Gemini: 695 managed tests passed, with no failures or skips and four
existing deprecation warnings. Test corrections, added coverage and independently
checked evidence are in [September 9 checkpoint regression](REGRESSION_2026_09_09.md).
No new live application was run for this checkpoint or regression. The Greenhouse
follow-up implementation and its synthetic validation are recorded separately below.

The [Greenhouse recovery and application progress plan](GREENHOUSE_RECOVERY_PLAN.md)
retains the evidence and requirements from attempt 45. The implementation adds
shared committed-selection read-back, private email-code handling, dispatch-scoped
employer rejection, authoritative metadata enrichment and semantic progress.
Synthetic validation is distinct from live acceptance; attempt 45 and production
application/mail records were not changed by this engineering work. Detailed test evidence and
remaining live-acceptance limits are in [Greenhouse validation](GREENHOUSE_RECOVERY_VALIDATION_2026_09_09.md).

### Shared recovery and progress contracts

Readiness and browser observations return `next_operation` with the actual
operation and parameter shape. Workday uses `fast_forward`; other forms use
shared Simplify controls. A fresh observation after work begins prevents a stale
startup Autofill recommendation. Readiness time and the first confirmed Autofill
dispatch boundary are recorded separately; `ready_to_autofill_seconds` measures
that gap without calling it model thinking.

The shared form reader associates selected labels/chips with one combobox.
Inventory, question capture, answer history and verification use that reader.
Native SELECT still compares the exact intended label/value. Search input text
and menu highlighting are not commitment. After activation, selection reacquires
a uniquely described control and requires two stable exact reads within the
existing bounded call. Results distinguish execution from answer commitment.
The executor decides recovery from scoped current options; the helper does not
turn a mismatch into an application outcome.

Verification email interpretation belongs to the executor using the existing
Hermes Gmail skill. The LLM selects the relevant code closest to the request
timestamp and polls again if mail is delayed. `hermes_gmail.py` is only a CLI
wrapper for that existing script and selected mailbox credential; it contains
no automatic message-selection or verification algorithm. The Google client
library used by that script is included in repository requirements.

The executor enters its chosen code through ordinary browser fill, or supplies
`value` to `credentials` mode `verification` with observed input refs. The
helper fills the fields and returns commitment without a mailbox lookup or
email-eligibility decision. Group/challenge matching, guessed length/format and
the twelve-field limit are removed. An observed resend control can be activated
without a recognized group; successful activation remains successful if the
next group is absent or ambiguous. It does not require an `email_code` classification.
Group completion reports nonempty fields; `maxlength` is not a minimum code length.
Optional message/timing metadata records the executor's selection. Code fields
remain masked in screenshots and excluded from saved answers. Employer feedback
establishes acceptance or expiry; a helper miss is a continuation, not an outcome.

`submission_state` projects `none`, `not_executed`, `pending`, `incomplete`,
`rejected` or `accepted` from the existing evidence. It is reporting, never form
permission. The ordinary shared submission path observes current required work
and private verification completeness, returns `application_incomplete` for
continuation, and captures confirmation before finishing. Each explicit Submit
can activate the current control once. Previous clicks do not prohibit fields,
mailbox/credentials, answers, reload/restart, pause/resume or another explicit
Submit. A targetless submit observes only. Workday follows the current page on
each advance call. The older Hermes worker's parallel click-history restriction
and mandatory internal resume-upload receipt were also removed.

`record_submission_rejection` remains a compatibility endpoint for precise
historical evidence; ordinary continuation no longer calls or requires it.
Structured dispatch/document/frame IDs retain their exact correlation values
instead of masking numeric UUID segments. Earlier dispatch evidence is preserved
when a new cycle or replacement browser target is observed. Only recorded
success suppresses an ordinary new request. Job status aggregates concurrent
attempts so a later failure cannot erase a successful application.

`enrich_job` and owned `observe_job_metadata` fill missing company/title from one
scoped posting or unambiguous Simplify job card, preserving nonempty labels and
recording provenance/conflicts in the existing job metadata. Normal shared and
Workday observations and answer capture call this path. `backfill_job_metadata`
defaults to preview and validates exact job/attempt association with retained
answer-history evidence; it changes labels only when explicitly applied. No
production backfill is implicit in startup, migration or tests. Queue, session,
focused-job and attempt views read these labels; unresolved discovery shows the
posting link and an honest identifying/unavailable label.

`progress(stage,activity,task_id?,state?,evidence?,next_step?,source?,action_id?)`
uses the existing event ledger and supplies valid event ID/time. Completion needs
evidence. Strict externally supplied `event` identity/time requirements remain.
Shared field actions, saved-answer application, required-question requests,
private credentials, Workday source/steps and submission emit stable stage/task
context with question labels only. Actions retain this context at start; outcomes
verify commitment independently of tool dispatch. Reports project all events
before limiting completed tasks. Unresolved tasks stay visible, recovered errors
close, raw chronology stays under Debug details, and refresh preserves expansion.
Elapsed wall time, explicit input waits and unioned action intervals are separate;
unobserved gaps remain unattributed. Legacy attempts show Details not recorded
when semantic evidence is absent.

## Before and after

```text
Before: conversation -> API token + running HTTP service -> expiring shared lease
        -> manually available browser/old target -> bounded helper
After:  conversation -> local start -> existing Service/database -> preparing session
        -> automatic workspace host -> verified fresh headed target
        -> existing Simplify/Workday/account/document helpers -> submission evidence
        dashboard + authenticated HTTP -> same Service/database
```

The previous coupling made service/token/browser setup prerequisites and treated
model gaps like loss of ownership. A small host without an LLM now retains the OS
lock and browser tree between CLI calls. Its cost is one host and one browser per
occupied workspace, bounded by configuration. No renewal loop grants permission.

## Responsibilities and records

| Component | Responsibility |
|---|---|
| Engineering agent | Shared code/skills and synthetic diagnosis; employer form work is not executor acceptance |
| Ordinary conversation | Selected model reasons, uses approved facts/mail/Simplify, handles exceptions, submits and verifies |
| Service/database | Eligibility, ownership, accounts, documents, actions, attempts, submission policy and outcomes |
| Workspace host | No model; OS ownership, automatic launch, readiness, scoped requests and stop-before-reuse |
| Workspace | Persistent authenticated Simplify profile, unique loopback CDP endpoint and browser instance |
| Dashboard | Observe same records and request independent pause/stop; optional for applications |
| HTTP | Existing authenticated compatibility API; cannot seize locally configured profiles/sessions |

One absolute configured `db_path` remains authoritative. `legacy_history_paths`
are read-only successful-submission sources; unfinished history does not suppress
a new request. Missing configured sources fail closed. There
is no cwd-selected database or second outcome store. `prepare_local` checks the
instance and makes an integrity-checked SQLite backup before migration 17,
which removes same-job uniqueness restrictions. Existing accounts, attempts and submissions remain. Transactions are short
state updates; browser/model/mail work stays outside them. Existing SQLite busy
handling remains in the shared connection layer.

| Record | Meaning and lifetime |
|---|---|
| Job | Canonical requisition, eligibility/outcome; persists across retries |
| Attempt | Execution history created after live readiness and retained |
| Session | One application's lifecycle and attached conversation; repeated start is idempotent |
| Workspace | Persistent directory/endpoint with one host; existing browsers allow multiple session-owned tabs, managed-process workspaces retain one session |
| Target | Fresh owned tab; never inherited from an earlier attempt |
| Account | Candidate + portal history; survives failed applications |
| Account coordination | Short person + portal lock during authentication; release after auth or stop; other portals independent |
| Host lock | Exclusive OS file handle held in profile until host exits |
| Process identity | PID plus OS creation time, protecting against PID reuse |
| Fence | Existing generation retained for service compatibility; local authority also requires session/current driver/host |
| Heartbeat | Driver activity telemetry, with no authorization expiry |
| Fast checkpoint/lock | Private counters plus OS lock for competing calls; not an outcome store; crash releases lock |
| Application question | Full required question, offered choices and context; exact job identity + candidate scope |
| Question answer revision | Immutable human answer/source/evidence/time; current revision uses optimistic concurrency |
| Answer retry request | Durable queued/started handoff to an ordinary harness; no model or browser launched when saved |

Account lookup precedes authentication and is scoped to candidate plus verified
portal namespace. `creation_pending` records dispatch intent; it does not prove
that an account exists. A creation click proven `not_executed` by the owned browser
can move its own attempt's pending account to `creation_not_executed`, retaining
the dispatch reason and allowing bounded recovery. Uncertain dispatch remains
pending for reconciliation. Workday uses a bounded retained-credential sign-in
check for pending creation, including a prior attempt, without recreating the
account. The native email chooser can recur once after creation. Employer
evidence establishes `created_unverified` or `confirmed`. Screen handoffs include
state, timestamps and last attempt ID.

Workday account creation and sign-in use the native retained-credential routine.
The shared Simplify observer/click boundary routes Workday authentication back to
`fast_forward`; a `credential_evidence` string cannot authorize extension account
filling. Stop/Cancel still settles an active extension operation. The runner keeps
the short blank-page transition after account creation in authentication and
returns application pages to Simplify after verified sign-in. This fixes the
attempt-34 recovery path: the executor supplied a credential reference to
Simplify's Sign In & Autofill, which does not establish the password it uses.
The existing private filler also retains a document-local credential receipt.
Routine and mapped Workday auth pass its opaque token to native activation.
The shared pointer validator rechecks and, if necessary, restores the retained
values after hover, immediately before the mouse press. The CDP result, account
checkpoint, helper report and timeline retain only match/refill booleans. No
password, password hash or reusable credential value enters those records.
This closes a reproduced late-autofill gap; it does not prove that Simplify
overwrote the password in the historical attempt.

Workday privacy acknowledgements such as "I have read and understood the Privacy
Policy" are recognized even without HTML required markers; marketing and job
alerts retain their existing exclusions. Manual auth-button clicks use the
matching same-form `click_filter` pointer surface, as routine auth already does.
A browser click may omit `page_signature`: the runtime still observes the owned
page and resolves the current ref before dispatch. An explicitly mismatched
signature returns the fresh screen and recovery guidance. These corrections
address Rakuten attempt 61's consent miss and manual-click failures; their
implementation alone is not evidence of employer account acceptance.
Synthetic regressions cover native creation/sign-in across a blank transition,
rejection of extension credential references, a login form appearing between
observation and click, and credential replacement after fill or hover while
preserving case-insensitive email matching. Validation: 671 managed tests passed, with four dependency
deprecation warnings; this does not establish live employer sign-in acceptance.

Job identity and browser ownership are distinct. The shared Workday parser uses
host, career site and the complete requisition (including suffixes such as
`R100_1`); locale, display location/title and application child routes do not veto
the same job. History, target checks and confirmation use that identity. Stored
URL hashes/history are not rewritten. An owned portal login is allowed; an
explicit redirect must identify the assigned job. Browser observation checks the
full URL before and after reading; public URLs omit authentication queries.
`different_job` and `identity_unresolved` refuse the affected form write while
preserving owned snapshots/screenshots and navigation back to the assigned job.
Navigation during observation prevents quiescence.

## Actual startup and call sequence

Configuration selection is `--config`, then `JOBBOT_CONFIG`, then the ignored
`artifacts/jobbot-v1-private/runtime-config.json` pointer containing `config_path`.
The selected private runtime is
`artifacts/jobbot-v1-private/windows-review-pilot/native-app.json`.
Use the actual checkout and its virtualenv. CLI reads `HERMES_SESSION_ID`, or takes
`--driver-id` with the actual conversation ID. Another conversation uses its own ID.

```text
.venv/Scripts/python.exe -m job_applier.application_runtime start <job-url>
.venv/Scripts/python.exe -m job_applier.application_runtime start --job-id <job-id>
.venv/Scripts/python.exe -m job_applier.application_runtime status <session-id>
.venv/Scripts/python.exe -m job_applier.workday_fast session <session-id> --seconds 60
.venv/Scripts/python.exe -m job_applier.application_runtime call <session-id> browser --parameters @<private-json-file>
.venv/Scripts/python.exe -m job_applier.application_runtime pause <session-id>
.venv/Scripts/python.exe -m job_applier.application_runtime attach <session-id>
.venv/Scripts/python.exe -m job_applier.application_runtime stop <session-id>
.venv/Scripts/python.exe -m job_applier.application_runtime retry <session-id>
```

These templates use implemented operations. `application_runtime doctor --url
<url>` is an optional read-only diagnostic, not a token/service/lease startup gate.
Generic local service calls use `run_applier.py managed call --config <path>
--transport local --operation <name>`; browser writes require the session host.

1. `application_runtime.start` resolves identity/config, checks read-only history,
   calls existing intake/eligibility, and selects the configured approved resume.
   `authorize_requested_urls:true` allows requested held URLs under standing
   authorization; exclusions and duplicate policy still apply.
2. `SessionServices.reserve_session` atomically records preparing/capacity_wait,
   candidate, resume, request/model evidence and an idempotency key. No attempt is
   created before readiness; repeated start for the same request returns that
   session/target. A fresh request starts a new attempt under RETRY_POLICY.
3. `ensure_host` automatically launches the no-model host. It checks ownership,
   launches the configured browser, verifies actual process arguments, profile,
   mode, endpoint and fresh operable target. It observes Simplify on the application
   surface; slow loading/missing panels return setup recovery on the same target.
4. `session_connected` creates the managed attempt and binds the fresh target.
   The compact handle resolves low-level IDs and includes existing application
   context: identity, approved assets, account strategy and helpers/lessons.
5. `session_call` sends JSON through a local Windows named pipe. Host dispatch
   supplies exact session/driver/host authority and invokes the shared operations.
   No HTTP token, model launch, global CDP setting or desktop focus is involved.
6. `workday_fast.advance` performs bounded routine observation/advancement using
   Simplify. The conversation handles actual blockers with scoped credentials,
   browser, account and mailbox helpers. Writer quiescence, forward-first behavior
   and selected-asset verification remain intact.
7. Existing submission_intent precedes one submit; finish records exact employer
   evidence. The host stops its browser before releasing the slot. Missing
   confirmation means inspect the current form and continue actual remaining
   work. Click history does not prohibit another explicit Submit.

Native Hermes jobbot operations are convenience calls to the same functions.
Hooks can record observed provider/model/effort; requested settings remain
separate. CLI-only model evidence is unknown unless supplied by the actual harness.

### Standard application request

Change only the URL. The canonical skills select the available ATS procedure;
the user should not maintain different prompts for Workday, Greenhouse or iCIMS.
An ATS appearing in this prompt is not a claim of verified support.

```text
Apply to [JOB_URL] using this repository's canonical job-apply skill.

Detect the application platform automatically—Workday, Greenhouse, iCIMS, or another ATS—and follow its available repository procedure. Use my configured approved profile, resume, retained credentials, managed runtime, and Simplify.

I authorize submission. Continue through supported recoveries and handle required fields using approved facts. Ask only for an unresolved verification challenge or missing required information. Do not change code, skills, or configuration.

Follow the canonical submission and confirmation procedure without adding a final resume or field audit. Inspect the current form and confirmation after an uncertain click; continue unfinished work and submit the current form when appropriate. A new user request can start a fresh attempt unless success is recorded.

Report the outcome and evidence source—or the exact unresolved blocker—with total elapsed time and session/attempt IDs.
```

## Windows lifecycle, recovery and parallelism

### Existing user browser (September 16, 2026)

A workspace can set `connection_mode: "existing"`. The default remains
`managed` for previously configured workspaces. In existing mode the user starts
Brave once, using `python -m job_applier.workspace_attachment --config <path>`.
Its fixed loopback CDP port and existing profile are read from the workspace;
optional `startup_urls` opens the dashboard and mail in order. A repeated launcher
call on an already connected browser does not create duplicate tabs. A normally
launched browser without debugging needs a one-time user close/reopen with this
launcher; an application executor never closes it or substitutes another profile.
The launcher omits `--enable-automation`, headless mode and port zero. It does not
override `navigator.webdriver` or browser fingerprints.

The host verifies the profile/port using OS process arguments (and Chromium's
profile lock for a Linux default profile) instead of
`Browser.getBrowserCommandLine`, which requires the automation switch. It creates
one application tab and records `navigator_webdriver` in readiness. This measures
the actual browser property; it does not predict or bypass an employer's challenge.
The shared browser process is never assigned to the host's kill-on-close process
owner. Existing user tabs and window size are retained.

Finish (including blocked/failed outcomes), Stop, Pause and same-attempt Restart
close only application-owned page targets and their discovered popup descendants.
Restart then opens a new application tab in the same browser and attempt. A unique
blank-tab marker and browser incarnation are saved before target creation, and the
target id is saved before navigation/readiness. Replacement hosts reclaim those
durable targets after a crash; a different browser incarnation is never cleaned
using stale target ids. Closure is verified before releasing the session. If the
application is the last tab, a neutral blank tab keeps the user's browser open.
A helper miss or time slice does not close the tab or invent an outcome.

The automatic queue's executor-exit recovery continues to request Stop, so an
executor that merely exits/chat-reports also releases its application tabs.
User-closed application tabs are observed and settled without closing other tabs.
Shared-browser retries retain cookies/storage because clearing an origin would
affect the user's other tabs. The managed-browser storage-reset policy below still
applies to managed workspaces. Retry scheduling and submission evidence rules are
unchanged. The UI/chat continues to show the recorded outcome.

The synthetic real-Brave fixture `test_existing_browser_live.py` verifies false
`navigator.webdriver` before/after attachment, in the application tab and after
restart; application popup cleanup; preserved dashboard/mail tabs and cookies;
idempotent starts, retry, host-death recovery, Stop and manual tab closure. It uses
localhost and a disposable profile, never employers or candidate records.

### Managed process ownership

`workspace_process` creates the browser suspended, assigns it to a Windows Job
Object with kill-on-close, then resumes it. The detached host retains that object
and the profile lock across CLI exit. Tests exercise real shell-exit survival and
child/grandchild death on host kill; detached Popen alone is not the proof.

A healthy owned browser is retained during its session. Current policy stops it
on finish/pause/stop instead of keeping it warm across applications; the persistent
profile remains. Idle hosts exit after 60 seconds. Externally running browsers
are never adopted or killed in managed mode. Startup checks endpoint and OS command-line inventory
before launching against a profile. Old profile aliases consult legacy reservations;
migration guards reject old-version acquisition of locally configured profiles.

New sessions for previously attempted jobs reset the assigned employer origin's
browser storage before navigating. Session reservation derives
`fresh_employer_storage` from related job/attempt and stopped-session history, so
retry commands, queued answer retries and new conversations follow the same rule.
After verifying its owned browser/profile, the host closes restored page tabs and
uses the page's [CDP Storage.clearDataForOrigin](https://chromedevtools.github.io/devtools-protocol/tot/Storage/#method-clearDataForOrigin)
with `storageTypes:all` for the assigned job URL's origin. It records the cleared
origin in readiness. Cleanup failure stops startup before employer navigation.
This shared path has no ATS-specific branch; first attempts and paused-attempt
attachments retain their storage. Simplify's extension and separate login origin
remain authenticated. Account records, credentials, answers and submission history
are independent of browser storage and are never reset by retry.
This is an origin-scoped reset, not a new empty browser profile: unrelated origins,
including separate third-party identity-provider origins, are preserved.

Validation passed all 694 managed cases before removing 15 redundant ATS URL
combinations. That storage-cleanup checkpoint collected 679 cases; the eight retained retry cases
passed again after that test-only pruning. Browser lifecycle fixtures now wait
for actual pause acknowledgement and continue a normal authentication `waiting`
response, retaining their account-count, ownership and confirmation assertions.
The primary engineering agent ran these checks. Routine delegated validation uses
the existing authenticated Antigravity Gemini 3.8 Flash Medium workflow; a requested
Antigravity rerun has not occurred while its launch awaits approval.

The two Workday entry dialogs are separate from cookie cleanup. The fast runner
can select the posting's Sign In control for a recorded account or pending
creation; Apply opens the application-method chooser. Clearing cookies does not
change that account strategy, confirm account creation or unlock an employer
account that rejects manual sign-in.

Pause/stop acknowledgement follows actual owned process-tree termination and
abortion of active actions. Startup observes pending control before connecting.
Explicit attach requires completed pause and creates a fresh target for the new
driver on the same attempt; the previous driver is rejected. Explicit retry stops the
particular session through shared control, then starts a fresh attempt. A new
request can use another workspace without stopping the prior session. An old
unresolved submission dispatch does not prevent this new request. After a crash, a replacement host
checks recorded process identities before classifying the lost session. It never
replays an uncertain command. Orphan activity/unconfirmed host launch remains
isolated with an actionable reason; a definitely unstarted failure releases its slot.

Host life, driver activity, browser writer state and verified progress are
separate. Driver age over 120 seconds is visible but does not revoke permission.
Host telemetry cannot manufacture progress. Optional maximum_runtime_seconds
(60..86400) actually stops the owned browser; it is not a lease timeout. Request,
preparing, connected and ended times preserve total elapsed wall time; queue and
startup time are available separately. Ten minutes is a measured target.

Two distinct configured directories/endpoints allow two independent sessions.
A third gets capacity_wait and occupants; repeated start retries capacity with
the same request. Paused sessions retain their physical slot until explicit
stop or retry replaces that session. The posting and candidate account are not
exclusive resources; another configured browser can use either. Same-job successful submission suppresses duplicates
across email identities. Earlier uncertainty does not. concurrency_limit caps use.

### Headless execution and visual evidence

The pointer validator reads the browser's rendered element bounds and
`document.elementFromPoint`, then the CDP client dispatches browser input. This
does not require a visible desktop cursor, an on-screen window or LLM image
inspection for every click. A screenshot is an available diagnostic for ambiguous
UI, not a prerequisite for routine DOM/pointer validation. Screenshot pixels alone
also cannot identify an invisible HTML click layer; control metadata is needed.

`WorkspaceHost.start_browser` already supports `--headless=new` for a headless
workspace; headed workspaces request maximization. Modern Chrome shares its
headed/headless implementation, as described in the [Chrome headless documentation](https://developer.chrome.com/docs/automation-and-testing/headless).
The existing `test_native_pointer.py` exercises native pointer input in an isolated
headless browser. These capabilities do not prove the configured Brave/Simplify
workflow, authentication challenges or complete employer applications work
headlessly. A future headless trial must verify the extension, viewport and
application flow separately; no mode/configuration change was made in this review.

## Configuration, provisioning and credentials

Local config requires transport:local, instance_id, absolute db_path, identity_id,
resume_asset_id, spool_dir, legacy_history_paths and workspaces. Each workspace has
id, absolute user_data_dir/browser_executable, unique 127.0.0.1 cdp_url and mode
(default headed). Optional legacy_profiles maps known earlier IDs. Preserve the
selected model/provider and explicit credential_profile_path, gmail_script and
mailbox_token_path references. Private config, assets, browser/auth state, logs,
backups, checkpoints and test artifacts stay out of Git.

Prepare each production workspace separately with official authenticated Simplify;
never clone live cookies/profile state. An empty second profile is an installation
gap. Readiness reports observed panel availability; slow loading or a missing
panel returns `startup_recovery` with the operable owned target retained. Process,
profile and target ownership still must be proven. The executor verifies actual
Simplify/account/contact identities. require_simplify:false is development-only.
Headless fixtures do not establish headless Simplify. Real official-service
concurrency requires two simultaneous authenticated extension sessions.

The portable CLI needs no native Hermes plugin installation. Native setup is in
[HERMES_CONNECTION.md](HERMES_CONNECTION.md). HTTP keeps environment-first,
explicit-file-fallback credential resolution, roles, instance checks and legacy
leases. Local execution uses OS/database access, not an unauthenticated network API.

## Helper map and canonical procedure

LinkedIn is a recognized platform, with application type observed separately.
Confirmed Easy Apply routes through `linkedin_easy_apply` (native Hermes and
portable session call), registered in `hermes_plugin` and `workspace_host`.
Startup, writer observations and shared snapshots supply the LinkedIn reference
and next operation. The helper attaches to the existing owned target and uses
shared writer, answer, selected-document and submission services. External Apply
retains its employer target handoff/ATS routing; bridge receipts and job/attempt
history are not migrated or rewritten. Missing direct URLs remain unclassified.

| LinkedIn helper/caller | Responsibility |
|---|---|
| `linkedin_easy_apply.py` | Approved answer batching, selected résumé recovery, Next/Review and shared guarded Submit; called by workspace host and Hermes operation dispatcher |
| `browser_helpers/linkedin_observe.js` | Donor-adapted modal/group/control discovery; called by shared form and writer observers, readiness and native helper |
| `managed_identity.py:linkedin_identity` | Explicit job-ID aliases across view/search/collection URLs without replacing stored keys |
| `third_party/godsscion-linkedin` | Pinned MIT license and source-to-local reuse map |


| Component | Scope and consumer |
|---|---|
| scripts/cleanup_validation_fixtures.py / jobbot-validation-cleanup.timer | Independent engineering maintenance of registered completed synthetic test directories; the daily user service verifies fixture identities, JUnit hashes and process references. Keeps reports and all application/private browser/history storage. No application executor, outcome, retry or deadline authority. See VALIDATION_STORAGE.md. |
| email_routing.py | Optional private Greenhouse route resolution, copied profile/contact-email answers and mailbox guidance; application_brief, managed_context, greenhouse_fast and hermes_gmail call it. No mailbox access or persistent writes; absent/disabled configuration preserves default behavior. |
| managed.py / migration 21 / managed_redaction.provenance_text / managed_views.py | Optional per-source process/run observations and per-queue-entry origin; numeric run identifiers remain intact, secret-bearing labels are redacted, and missing attribution does not affect eligibility. Dashboard/manual CLI/application startup and discovery supply process identities at their own boundary; rediscovery retains prior observations. Operator `reconcile_job_route` validates a bridge source/evidence before adding an external application alias and changing only a safe, non-running job's future execution URL; Easy Apply retains the posting URL. See SOURCE_PROCESS_ATTRIBUTION.md. |
| managed_queue.py / queue_runtime.py / migrations 22, 25 | Automatic active-intake pickup from worker and Run next; operator-selected concurrent dispatch and six-attempt retry lineage. Dashboard queue_enqueue(start_now=True) atomically promotes the chosen job and wakes the worker, bypassing its retry delay; durable immediate requests start in request order even with automatic scheduling paused, without interrupting active applications or rewriting attempt history. |
| hermes_desktop.py / application_brief.py | Optional application dispatcher transport creates a native session in the existing Hermes desktop backend; desktop resume and correction use that same owner. queue_runtime.dispatch_startup calls backend_ready for a bounded, read-only startup probe before reserving work. A private receipt reconnects the monitor without replaying the prompt; queue recovery checks the native turn after a monitor crash. The brief exposes the exact selected candidate email for comparison with observed form values. |
| managed_discovery.py / migration 20 | Selected-instance discovery run/check history and last/next-run reporting for the dashboard and harvest scheduler; no application dispatch or browser ownership |
| harvest_runtime.py / managed_settings.py / jobbot-harvest.timer | Minute schedule checks launch fresh Hermes discovery only when the saved interval is due; dashboard settings own batch size and interval; the existing harvest lock prevents overlapping discovery; optional harvest_hermes_command selects a discovery profile, and unfinished private checkpoints carry verified leads into the next run for revalidation |
| application_runtime.py | Shared request identity, start/retry and stop/pause lifecycle; early platform/reference guidance, scoped browser actions, pre-click external Apply and authentication target observation/handoff, automatic masked-image recovery after snapshot misses, field attribution, Autofill timing and answer/metadata capture |
| managed_sessions.py / migrations 15 and 17 | Session and physical workspace allocation, first-attempt/reattempt metadata and history-derived storage cleanup; same-job and account-use exclusion removed. The host-only target handoff atomically retains the prior owned tab and changes the session target after correlated Apply or authentication navigation; the latter retains the verified employer account URL. application_job projects that ownership-checked full route for managed helpers and managed_runtime.browser_observe; the intake posting and query-stripped target display remain separate. |
| workspace_host.py / workspace_process.py | Windows lifetime/readiness timing, durable same-attempt restart preparation through verified close/reopen, employer-origin cleanup for managed-process retries only, concurrent JSON dispatch per owned session in shared browsers. prepare_target creates a visible window per application and calls arrange_application_windows to tile only its owned windows for Simplify's visibility-dependent filling; no model or five-second busy veto. |
| workspace_attachment.py / workspace_host.py / managed_sessions.session_browser_attachment | Existing-browser launcher, persistent `watch_browser` supervision and verified attachment; durable application-tab ownership, tab-only cleanup/recovery, and observed navigator.webdriver. Called by the manual launcher, jobbot-browser.service (`--watch`) and local host; queue_runtime.dispatch_startup reuses read-only profile/process and endpoint checks before native desktop dispatch. Managed process lifecycle remains available. |
| managed_client.py / managed_cli.py / managed_api.py | Two transports over shared methods; HTTP auth retained |
| static/jobbot.js / managed_api.py / managed.py.update_job_url | Operator URL corrections retain the job number, added date, outcomes, source references and old identity aliases; save normalized replacement aliases and an audit trail on the same job. Sorting and filters use existing job data in the dashboard. |
| static/jobbot.js / managed_queue.py | Queue selected sends visible selection in table order as one immediate request; queued items are reused and receipt insertion order breaks equal-time ties. Repeated requests retain their original position; a new manual selection can reorder its waiting jobs. Current applications continue, automatic scheduling remains enabled or paused as configured. |
| managed.py / managed_runtime.py / managed_events.py / managed_views.py / managed_continuity.py | Existing policy/actions/events/duplicates consult local lifecycle or explicit legacy ownership |
| managed_identity.py | Workday host/site/full-requisition and iCIMS host/job-id comparison, history equivalence, application scope and diagnostic match states; Rippling locale presentation is ignored only on its hosted tenant/full-UUID route, and Dayforce locale presentation only on its hosted tenant/CANDIDATEPORTAL/numeric-posting route. Existing frame router, runtime, credentials and binding callers share scope matching; intake URLs and history keys remain unchanged. |
| route_history.py / managed_sessions.handoff_target | Called by managed_runtime.browser_observe before scope reads; retains local owned main-document history evidence and atomically projects delayed same-origin continuations. A fenced retained history source remains valid after an accepted Apply handoff changes the target key; source, browser/session/target/fence, current identity and same-origin/conflict checks still apply. The iCIMS reader refreshes context through this shared observer before inspecting a changed embedded form. No browser writes, account migration, retry decision or application outcome. |
| managed_shared.submission_state / submission_pending and managed_events._submission_state / _submission_pending | One per-attempt evidence projection from existing ordered events; evidence reporting only; accepted alone suppresses a new requested attempt |
| greenhouse_fast.py | Session-owned `greenhouse_advance` residual batches; next_operation/startup guidance, local workspace host and nonlocal plugin dispatch call the same advance entry. Simplify remains the bulk filler. Legacy platform_handlers/greenhouse.py stays available to its existing agent/registry callers. |
| icims_fast.py | Thin `icims_advance` runner called by native plugin, portable CLI and workspace host; reuses shared writer/identity checks, audit, private credentials, approved answers/policy, grouped repair and final submission. Posting Apply calls the shared application_runtime target-handoff observer. Slices/unknown controls return to the same executor. |
| form_audit.py | Pure compact projection of the shared inventory; `browser(method="audit")`, post-Simplify handoffs, snapshots and iCIMS use the same required/invalid/private/optional classification. No independent scanner, writer permission or outcome authority. |
| workday_fast.py | Bounded Workday supervisor, direct application entry and source-choice recovery; native and CLI call the same advance function |
| workday_auth.py | Workday account decisions inside the supervisor; shared account record/coordination and private filler, no model or password storage duplication |
| cdp_client.py | Exact-target connection, correlated same-tab/popup observation for an armed external Apply destination (including about:blank transition), verified document reload, structured evaluate_function arguments, and validated native pointer activation shared by the runner and local browser recovery |
| browser_controls.py / browser_helpers/form_controls.js | Shared form reader including Apply, committed-selection verification, posting metadata, private code groups and remaining_submission_work; iCIMS entry guidance; used by submission, browser runtime, answer capture, credentials and Workday |
| browser_frames.py / cdp_client.py channels | Shared DOM-owned application document routing below the existing browser API, isolated worlds, stale-ref rejection and root pointer mapping |
| managed_queue._settle_reconciled_queue | Called inside successful manual reconciliation; atomically settles only queued rows for the related job and same identity. Existing stopped-session/newer-attempt checks and dispatched/history rows remain intact. |
| managed_answer_library.py / migration 26 | Current candidate-scoped knowledge, aliases, applicability, append-only revisions and synthesis provenance; called by profile writes, question capture, operator APIs, application context, shared saved_answer and the dispatcher minute reconciliation. No browser/helper outcome authority. |
| answer_learning.py / answer_learning_model.py / migration 27 | Dashboard-owned background synthesis, equivalent-answer merging and question wording review; uses the installed Hermes auxiliary inference client without application tools/sessions. Called by queue_runtime.serve; human saves enqueue durable inputs in the same database. No application/helper outcome authority. |
| job_duplicates.py / migration 29 | Called by configured intake, the dashboard background worker and shared admission checks. Optional cached local embeddings propose same-company role matches; matching_suppression rechecks candidate success or explicit operator cancellation for new admissions in enforce mode. Stores reversible pair decisions and first actual skip receipts with the real reason, without creating URL/ownership aliases or copying dispositions. |
| daily_summary.py / hermes_notifications.py | The existing notification watcher calls a read-only calendar-day projection at the configured morning time. Counts submissions, attempts, actual duplicate skips and sixth-dispatch exhaustion; private delivery receipts prevent ordinary restart replays. No application outcome authority. |
| managed_questions.py / migrations 16 and 26 | Durable required questions, exact human answers/revisions and retry requests in the same database; browser-independent, success-only history suppression shared with ordinary starts |
| application_answers.py | Shared label_has, match_answer_to_option, approved_answer, answer_action and saved_answer (re-exported by LinkedIn); approved Greenhouse plan journal restoration; interprets profile salary/privacy preferences and retains best-effort private question/answer history from shared browser writes, mapped recovery and Workday advancement; contains no personal answer defaults |
| submission.py / browser_helpers/submission_observe.js | One activation per explicit call, current incomplete-form continuation, retained dispatch evidence and native/Simplify confirmation; local browser and Workday callers |
| hermes_notifications.py / jobbot-notifications.service | Independent read-only submission-ledger observer; calls the installed Hermes send CLI for confirmed applied company/role alerts, with private durable delivery receipts and retries. No application/helper or answer-reply ownership. See SUBMISSION_ALERTS.md. |
| simplify_boundary.py / browser_helpers/simplify_observe.js / simplify_click.js | Shared initial-Autofill recommendation, dispatch/step receipts and settlement for all portals; called by browser routing, iCIMS, LinkedIn, Workday, Greenhouse and legacy handlers/worker. Greenhouse retains its eligible residual second pass; explicit recovery remains available. |
| platform_handlers/base.py / workday.py / greenhouse.py / registry.py | Legacy agent callers share SimplifyBoundary through the existing CDP page or actor evaluation adapter before native form work/recovery. Missing controls and helper failures return to the existing executor with visual-recovery context. |
| browser_helpers/workday_observe.js / workday_click.js | Workday steps/errors/attachment/employer-confirmation and observed controls |
| browser_helpers/workday_source.js | Workday-only recruiting-source field/menu association, live option inventory and virtualized-menu scrolling; workday_fast drives pointer actions and verifies commitment |
| managed_credentials.py / managed_documents.py / hermes_gmail.py | Selected account-field filling, executor-supplied code entry without group/format permission, existing Hermes Gmail CLI wrapper, code screenshot masking and selected uploads; workspace host, legacy plugin and Workday callers |
| portal_credentials.py | Private-file portal password storage and scoped resolution; operator account services write overrides, dashboard views project source labels, and managed_credentials resolves values for local and legacy managed fillers. |
| legacy_credentials.py | Private per-account password persistence for the original browser-use agent, element handler and Workday platform handler. Replaces their shared built-in creation password; does not change managed credential references. See [Legacy application](../LEGACY.md). |
| managed_shared.py / managed_events.py / managed.py | Common submission resolution, strict evidence ledger, progress convenience, existing job metadata enrichment and previewable backfill |
| managed_reports.py / managed_sessions.py / managed_views.py | Stage/task projection from the same events and actions, explicit waits/action overlap, shared labels and first-Autofill timing |
| hermes_plugin.py / integration entry | Convenience, actual conversation/model and observed request-turn identity, current session binding after retry, optional messaging capability metadata and observed human-reply provenance; no alternative form logic |
| managed_hermes_worker.py / native_hermes_session.py / hermes_adapter.py | Existing explicit legacy worker integration; never launched by local start |
| static/jobbot.html / jobbot.js / jobbot.css | Shared posting labels and stage/task progress, persistent expansion and collapsed technical debug, independent application controls |

Common policy is job-apply v0.5.9; Workday policy is workday-simplify v0.3.16, in
skills/productivity. Hermes discovery is thin. Source fingerprint/revision and
canonical skill hash are recorded at start. No shared helper/skill edits during
an application benchmark. Review observations afterward and load the revision
on the next application. Trace all callers before declaring older helpers unused.

Optional `answer_policy_profile_path` selects a private editable JSON profile.
Only its allowlisted `application_answer_policy` preferences are projected into
the managed candidate at start, before the immutable attempt snapshot. Other
candidate fields stay managed; credentials remain in `credential_profile_path`.
Without this option, the managed profile remains the source. Supported policy:
`salary_expectation:{use_posted_range_max,fallback_amount,currency,period}`,
`routine_privacy_consent:boolean`, and `submission_evidence_sources` containing
`employer`, `simplify`, `user_reported`. Fallback is not a minimum/floor. Multiple
advertised ranges require the applicable range from the executor. No historical
attempt answer or outcome is rewritten when preferences change.

Submission capture is armed on the owned CDP target before activation. Evidence
survives ordinary scoped redirects and is persisted in the private spool. A
possibly dispatched submit is never replayed. Native and Simplify proof carry
separate sources; absence of approved evidence returns uncertainty. Local hosts
retain that page until completion, requested Stop or the configured maximum
runtime; there is no additional two-minute inspection deadline. Proven
`not_executed` dispatch or a fresh dispatch-scoped employer rejection permits
recovery in the same attempt. An intent with no
dispatch result remains uncertain. Reconcile supports the native plugin and portable CLI, records a
separate source/timestamp event, and preserves historical completion/duration.
Headed browser startup requests and verifies maximization; no automatic refresh.
One background host owns each occupied workspace, with independent parallel
session cleanup. It exits after a completed session response is delivered.

Enabled Simplify input prompts can override a cosmetic spinner after stable
observation, while real unfinished helper writes remain exclusive. Native
takeover remains separate from extension input permission. Shared form helpers
verify values and return ambiguous menu/coverage evidence instead of guessing.

An unknown writer can settle through fresh stable extension evidence (including
explicit unsupported/idle state), or the observed Simplify Stop/Cancel autofill
control via `browser simplify action:stop`. This narrowly scoped cancellation is
available to the owning local host while the extension state is active/unknown;
an unended host write still excludes another write. Stop does not declare idle:
the boundary observes stable settlement. Missing or unrecognized stop controls
retain uncertainty and return inspection. Inaccessible-frame diagnostics affect
that document's controls; readable documents retain their own routing/validation.
Local semantic timing remains telemetry and does not veto an otherwise valid
write. Legacy configured strategy checks remain on their existing callers.

After one available page Autofill settles, Workday prefers enabled native Continue in `needs_review` so that a populated
source answer such as LinkedIn does not reopen Simplify's review menu. At authorized
Review it submits without another resume or field audit. Missing attachment
evidence is not a final-submit gate. The same-portal
`jobTasks/completed/application` route is a read-only confirmation surface;
fresh approved Simplify success is sufficient without waiting for employer mail.

The existing private spool stores `answers/attempt-<id>.json`, captured during
filling and advancement. It includes company, ATS, portal namespace, job identity,
attempt/session, full question and answer, timestamp, source and available answer
basis. Repeated read-back is deduplicated; changes remain in history. Missing basis
is explicit, not inferred from a favorable answer or promoted into profile facts.
Credential, verification-code and financial-identifier controls are excluded.
Timeline checkpoints and browser results link the artifact; this does not add
another database or a final-review pass. Audit errors are reported separately
and never imply that an executed form action is safe to replay.

### Shared embedded forms and human answers

The harness uses one `browser select`/`fill`/`check` interface. Observed refs carry
document identity internally; no model chooses an iframe or Workday handler.
Non-Workday inventory includes visible DOM-owned application iframes, including
cross-origin OOPIFs, without looking for other tabs. Discovery uses the assigned
employer page's explicit application embed and rejects contradictory requisition
IDs. Workday keeps its existing observer and fast runner. Same-origin and
cross-origin native selects, ARIA menus, uploads, private credentials, answer
capture, credential masking and Simplify actions share this routing.

Refs survive a new CDP connection to the same document, but not navigation,
replacement or changed ownership. Native pointer input validates the child and
every parent iframe hit target before dispatch; overlays cannot be forced through.
Traversal is bounded to four levels, twelve application frames and the first
24 iframe owners per document. Transforms/zoom that prevent reliable coordinate
mapping and unverified redirects return diagnostics. This is shared plumbing for
recognized embedded forms, not a claim that every custom widget or ATS works.

Submission arms the parent and selected embedded document before the single
intent/click. Child confirmation is tied to its original frame ID and application
URL, including after a normal scoped redirect. Replacement frames and conflicting
query requisitions cannot supply proof. Transient messages are retained. A repeat
call after uncertain dispatch only observes; it never clicks Submit again.
Custom employer `/jobs?gh_jid=...` and `/form?gh_jid=...` aliases now also match in
intake and read-only history; meaningful unknown query keys remain distinct.

Missing facts use an additive durable queue, separate from the private observed
answer audit. `browser request_answers` first applies approved salary/privacy
policy and exact saved human answers, then queues only the remaining missing
required questions from current controls. Simplify and the executor use approved
facts before invoking that queue. Optional answer-history/progress-event errors
remain diagnostics; action ownership, dispatch intent and outcomes remain mandatory.
Failed menu interaction is a technical diagnostic, not a human question. Answers
are scoped by candidate, verified job identity, exact field/question/options and
page/section/document. Reordered or changed choices are not guessed equivalent.
The current answer can change through an optimistic revision; earlier answer
records remain immutable. Choice objects include both value and label, avoiding
duplicate HTML-value ambiguity. Passwords and verification/financial identifiers
are excluded. Approved facts are never reconstructed from a resume during a run.

`human_input` is a harness capability declaration, defaulting to no messaging and
the dashboard queue. The core imports no Discord or Hermes service. Hermes derives
availability from its actual conversation platform or offered messaging tool;
its `answer` bridge requires an observed user turn newer than the question and
its last answer, and stores a turn ID/hash as provenance. Other harnesses can
declare the same capability at start or use the dashboard without messaging.
Capabilities do not grant permission to send a message or choose a recipient.
CLI answer writes require explicit user-reply evidence. Late replies only update
answer data; they do not reclaim a stopped browser.

`park_questions` records a blocked attempt and requests stop. Host acknowledgement
releases browser/portal ownership and the slot, unlike pause. The dashboard reads
the same database and offers Save answers, Save and queue retry, and a batch queue
button. Saving never starts a browser. `answer_retries` lists ready requests for
the configured candidate; an ordinary authorized harness starts each with the
returned job/request IDs. `session_connected` marks its request started. No
scheduler or extra LLM is created. `browser apply_answers` checks current refs and
the exact question before applying a saved answer and recording its provenance.
Same-job recorded success suppresses retries across email identities. Actual
browser ownership must end before queueing. Uncertain history remains retryable;
queueing does not rewrite or reconcile the earlier submission evidence.

### Learning from successful and blocked applications

Use the existing managed attempt ID to join outcomes/timing, code and skill
versions, actions/events and the private spool artifacts. Keep the design/change
history in RUNTIME_SIMPLIFICATION_LOG rather than relying on an engineering chat.
Keep individual failure/recovery narratives in the managed database, linked to
their attempts; design documentation explains the resulting architectural choices.
Record both successful and blocked applications: successful work establishes
which recovery and answer paths were useful, while failures identify unmet cases.

| Existing record | What it contributes |
|---|---|
| Managed jobs, attempts and sessions | Employer/ATS/job linkage, final status, evidence source, original timing, driver and source version |
| Actions and event timeline | Stage, selected operation, coarse action result/duration, recovery reason and verified milestones |
| Private `answers/attempt-<id>.json` | Observed questions/answers, company and portal metadata, changes, provenance and any recorded answer basis |
| Private submission capture and screenshots | Observed native/Simplify confirmation or remaining uncertainty; source stays explicit |
| Private fast checkpoint and executor tool results | Detailed dispatch and control evidence when retained; a checkpoint is mutable working state, not a complete immutable action history |
| Retrospective operator checkpoint events | Per-attempt diagnosis, attempted recovery, evidence, resolution and provenance without rewriting execution history |
| Implementation log | Architecture, implementation rationale, checkpoint validation and deferred design proposals |

For comparisons, identify the failure mechanism (for example, a covered control
with proven non-dispatch), not only the final generic blocked/budget-limit label.
Include the attempted recovery, whether input actually dispatched, latency and
result. Separate repeated attempts on one job from independent employers/jobs;
otherwise retry-heavy debugging can distort the apparent incidence and success
rate. A submitted application is not a hiring acceptance. Later employer replies
belong to separately sourced recruiting outcomes, as described below.

Current coverage is incomplete: `action_end` records coarse status, the fast
checkpoint retains the latest dispatch, and some details remain only in executor
tool results. Historical missing answer bases and dispatch reasons remain missing.
Recovered diagnoses are stored as operator checkpoint events with
`operation:attempt_diagnosis`, `source:operator_postmortem` and structured
`category`, `error_type`, `reason_code`, `evidence`, `fallback_reason` and
`resolution` fields. Annotation timestamps describe the later review, not a
fabricated execution-time observation. Post-completion events have `stale:1` to
avoid creating active progress; they still appear in the full attempt report.
They do not alter the original outcome, timing, account state or action history.
No automated cross-attempt analysis or universal detailed failure-event capture
is claimed; these retrospective notes supplement the existing automatic records.

For a read-only review of the selected managed database:

```sql
SELECT attempt_id, recorded_at,
       json_extract(payload_json, '$.error_type') AS diagnosis,
       json_extract(payload_json, '$.evidence') AS evidence,
       json_extract(payload_json, '$.resolution') AS resolution
FROM managed_events
WHERE actor = 'operator'
  AND json_extract(payload_json, '$.operation') = 'attempt_diagnosis'
ORDER BY attempt_id, recorded_at;
```

If review shows recurring evidence loss, add the minimum sanitized fields to the
existing event/report path before considering another data store. Do not copy
passwords, mail bodies, full profiles or unrestricted DOM dumps into Git/logs, and
do not replace historical outcomes merely to simplify analysis.

Follow-up work: schedule confirmation-email correlation about 30 minutes after
submission through the existing Hermes Gmail adapter (employer, requisition/title,
recipient and attempt time; deduplicate by message ID and never treat delayed mail
as failure). Keep accepted on-page success final without waiting for this follow-up.
Later extend the same correlation to rejection, interview and recruiter-response
updates, retaining each message's source/time separately from the original
submission outcome. Ambiguous mail should await classification, never update a
different requisition. These email automations are deferred, not implemented here.
Add a candidate profile
editor exposing advertised minimum/maximum choice, fallback amount, currency,
period and routine consent; keep preferences in editable data and snapshot the
chosen policy for each run. Minimum-range selection is a future option; this
checkpoint implements the approved maximum/fallback policy.

## Verification boundaries

### Historical design: shared embedded forms and unresolved questions

The following is the retained design rationale from before the embedded-form and
answer-queue checkpoint. Current implemented behavior is described above; this
historical plan is not the execution contract or a live acceptance claim.
The existing dropdown operation supports native selects and associated ARIA
menus in the document it can inspect. A form inside another frame is a separate
observation/action-routing gap: adding more option-label matching alone will not
make those controls reachable. Employer-hosted Greenhouse validation exposed
that boundary; detailed application evidence remains in managed attempt reports.

The next delivery should extend the existing shared browser/form helpers with a
small frame-aware adapter. Keep Simplify as the bulk filler and retain the
existing application runtime, browser profile, assigned target and lifecycle.
This is not a separate Greenhouse application runner or a per-employer script.
Use the same form operations for controls in the top document and in a verified
application frame. Same-origin and cross-origin frames are separate test cases;
the latter cannot be traversed using ordinary parent-document selectors.

| Responsibility | Proposed scope and boundary |
|---|---|
| Frame discovery and routing | Associate the frame with the owned parent target and verified employer/requisition. Do not select arbitrary frames, ads, challenges or another job solely because they contain inputs. |
| Control references | Bind each observed ref to its document/frame and observation. Resolve selection, checking, filling and pointer validation in that document; reject detached, navigated or ambiguous frames. Keep Simplify panel refs distinct from employer-form refs. |
| Value operations | Reuse native-select and associated-menu behavior, including exact option matching and read-back. Preserve frame offsets and coverage checks for pointer input; do not substitute guessed coordinates or force clicks. |
| Submission and evidence | Route the observed frame control through the existing one-click submission boundary. Arm confirmation capture before dispatch, retain parent Simplify and native frame evidence with their sources, and do not automatically replay an uncertain dispatch within the same attempt. A new requested attempt follows the shared retry policy. |
| Redirects and job identity | Recognize the same requisition across verified posting/form routes, including meaningful query identifiers. Reject conflicting job identifiers; do not authorize every same-host path. Link verified aliases through the existing identity system without rewriting historical jobs. |
| ATS recognition | Use observed embedding evidence for custom hosts. Recognition may select ATS-specific procedures, but generic form operations should not depend on a Greenhouse hostname or employer name. |
| Answer policy | Present approved facts, explicit user answers and existing answer defaults consistently to the executor. Preserve contrary facts, question-type boundaries and configured exclusions. Record whether an answer came from a fact, user instruction or approved default. |
| Routine privacy consent | Extend the shared policy from checkboxes to observed select/menu acknowledgments. Require an unambiguous consent option and continue excluding marketing and job alerts. |
| Required questions | Distinguish native required/validation evidence from Simplify review warnings. Leave optional unanswered fields alone unless separately requested; use the answer type rather than applying a yes/no default to a country or text question. |

Workday retains its existing page recognition, authentication/account sequence,
mapped recovery and fast runner. Shared changes can still affect Workday, so
preserving that dispatch path is not sufficient evidence of compatibility.
Regression coverage must exercise its use of the shared helpers. Do not fold the
deferred Workday authentication exception into this delivery.

Before implementation, add focused failing regressions using synthetic forms and
isolated browser profiles, never live employer applications or production data.
Cover top-level forms, same-origin frames, cross-origin frames, ambiguous frames,
frame rerenders/navigation, populated selections, consent dropdowns, required
versus optional questions, parent overlays and frame offsets. Include verified
same-job redirects and different-job query rejection. Exercise single submission,
native/extension confirmation and uncertain-dispatch protection with fake
employer endpoints. Run relevant Workday authentication, mapped recovery,
pointer, answer-history and confirmation checks, then one final managed suite:
`.venv/Scripts/python.exe -m pytest tests/jobbot_v1 -q`. Browser fixtures establish
mechanism coverage; later ordinary authorized applications establish live ATS
acceptance. Runtime/skill changes must happen outside application benchmarks.

A second delivery can add a shared **Needs your answer** review queue. Current
answer history records observed answered questions; it is not a durable queue of
unanswered questions/options and the dashboard has no response editor yet.
Persist the exact unresolved required question, response type, observed options,
job/candidate context, reason for escalation and subsequent user answer with
provenance in the existing managed data/artifact system. Use approved facts and
applicable defaults before asking. Do not treat a control-access failure as a
request for the user to invent another answer.

The dashboard is the durable review interface: **Save answers** leaves the job
for a later batch; **Save and retry** requests an ordinary managed continuation.
Keep unresolved jobs out of that batch. Match saved answers to fresh questions
and options; old DOM references must not survive into a new session. Answers are
application-scoped unless the user explicitly approves broader reuse. An
uncertain prior submission remains truthful history and can receive a fresh
answer-driven attempt unless successful submission is recorded.

Hermes Discord can be an optional notification/reply channel over those same
question records, rather than a separate workflow or bot service. Deployment
credentials and channel routing remain in the private Hermes configuration.
Correlate authorized replies with a specific question and application. A quick
reply can continue an owned, quiescent live session; otherwise preserve the
question and release the workspace through the managed lifecycle so unrelated
applications can proceed. A chat message saying "paused" is not a lifecycle
transition, and a paused session currently retains its workspace slot. Define
the bounded waiting/parking behavior as part of that second delivery.

Implementation documentation and PRs must distinguish proposed, fixture-tested
and live-verified behavior. Identify the motivating Greenhouse validation and
related attempt IDs in the PR; keep full employer-specific diagnoses in managed
history. Update this helper map and canonical instructions when actual caller
responsibilities change. No Discord notification or application retry is
authorized merely by documenting this design.

### Current implementation

Snapshot and Workday recovery share one native/official-extension inventory in
workday_fast.observe_page/screen_inventory. workday_observe retains unique
semantic refs across routine rerenders; the existing private filler and native
click helper accept those exact mappings. fast_forward recovery performs a bounded
mapped fill/verify/action/observe step in its existing connection, then resumes
routine execution. Mapped decisions and possibly-executed actions persist in the
existing private checkpoint; actual authenticated form access confirms the account.
No new service, migration or execution framework is involved. Workday sign-in
uses native retained credentials; the shared Simplify click path rechecks for
authentication before acting. Simplify account actions and a credential-reference
string cannot replace that routine. The older Simplify sign-in interface remains
for other ATSs and distinguishes employer from extension login.
Settled unrecognized UI returns actionable context promptly; writer uncertainty
remains an observation-only condition. Accepted mapped-step counts are recorded,
but are not a measurement of every model interpretation outside this interface.

The shared credential resolver selects the account ledger's saved reference. The
canonical default is credential:profile/accounts/default, resolved privately from
the explicitly configured credential_profile_path accounts.default. Optional
credential_account_keys maps a saved reference to another account key in that
same configured private file. An unavailable saved reference fails specifically;
it never silently borrows the default password. No credential values enter the
managed DB, events, helper checkpoint or model output.

Selected sign-in controls may contain email only, password only, or the whole
form. A revealed password input is supported. Existing candidate/account identity
matching remains. Actual missing controls, unavailable saved
credentials and browser failures remain reported; they are helper diagnostics,
not application outcomes. The [error-return review](ERROR_RETURN_REVIEW.md)
records these removals and the retained checks with their reasons.

For local Workday sessions the fast runner supplies the existing session account
coordination callback to workday_auth. It performs one fresh observed action at
a time, including the account privacy/terms checkbox and disabled-until-filled
submit buttons. It persists creation_pending before creating, records an explicit
employer creation confirmation immediately, and confirms sign-in only on an actual
application form. Counters survive calls and prevent replay of uncertain account
actions. Mail verification, rejected credentials, ambiguous consent or unfamiliar
controls return a specific authentication_required result to the ordinary executor.
The browser remains available for scoped recovery. Other ATS and legacy HTTP
execution retain their existing executor-driven auth path using the shared filler.
Simplify-generated password capture is not implemented: no documented retrieval
contract has been verified, so the current flow uses retained configured credentials.

Authentication handoffs distinguish unsupported/possibly changed controls from
rejected credentials, verification, configuration and an unconfirmed action. They
return observed non-secret control metadata, an owned screenshot command and a
bounded recovery instruction for the current executor. The reason/next step is
persisted once in the existing recovery timeline. browser screenshot writes a
unique PNG beneath the configured private spool, masks credentials with the same
shared mask as the legacy browser, and restores it even if capture fails. The
ordinary Hermes vision_analyze tool accepts that local image path; snapshot returns
fresh selectors for the subsequent scoped action. Missing vision capability stays
explicit and DOM inspection remains available. The runtime launches no model or
additional worker; the harness uses its existing image capability (native vision
when supported). This path never switches browser profiles or edits helpers in-run.

The existing immutable event timeline carries executor stage/activity/next-step
updates, helper observations and recoveries. Session cards show the latest semantic
update and recent steps, separately from host/driver liveness. The Workday runner
records a changed step/action once rather than on every poll. The host records a
helper exception and returns it without ending the session; the executor chooses
the supported recovery and records its explanation. Neither an activity update nor
a successful low-level tool call proves form progress. Old attempts without these
updates remain incomplete evidence and are not backfilled as successful steps.

Final automation runs the supported python -m pytest tests/jobbot_v1 -q suite,
with JOBBOT_BROWSER_TEST_EXE enabling real Windows lifecycle coverage. Destructive
checks use synthetic DBs/profiles. JUnit and phase evidence stay in ignored artifacts.
Official Simplify, mailbox challenges, employer submission and under-ten-minute
performance require separate ordinary-Hermes evidence. The implementation log
contains actual commands/results, durations and remaining blockers.
# Queue and VM additions — 2026-09-15

The queue view projects retained `job_sources`, original intake time and the latest
recorded operator/application/dispatch disposition. `harvester_source` converts
saved Harvester JSON/CSV to offline discovery leads; `harvest_runtime.harvest_brief`
can reference them through optional private `harvest_leads_path`. Existing discovery
verification and `intake_results.py` remain the only publishing path. No live pull
connector or additional dispatcher was added. See [Harvester integration review](HARVESTER_INTEGRATION_REVIEW.md).

Operator cleanup now uses a reversible Canceled disposition in the same managed
database (migration 19). `managed_archive.set_job_disposition` owns the mutation,
`managed_events._control` shares run stop requests, and
`Service._assert_not_suppressed` excludes explicitly canceled postings until
restored. The dashboard's bulk selection, filters and collapsed session history
are documented in [Job cleanup](JOB_CLEANUP.md). No automatic failure-based
restriction is introduced; account and application evidence remain intact.

The current runtime can now be called by `job_applier.queue_runtime`, a separate
dispatcher (concurrent since October 2). `managed_queue` owns explicit queue records (migration 18),
`application_brief` assembles one fresh job's skill/mail/vision/Simplify context,
and `harvest_runtime` launches a separate discovery task. The canonical apply
runtime and its ownership/evidence rules remain authoritative; legacy HTTP
accept/claim does not become the new local dispatcher.

September 16 queue recovery follows desktop replacements using the private
dispatch receipt's exact conversation, job and candidate. `queue_runtime.find_sessions`
is the common association reader for settlement and restart recovery;
`hermes_desktop.orphan_is_active` checks current native ownership even when an
old receipt says finished. Ended native work releases retained browsers through
the existing host stop/acknowledgement lifecycle, including sessions opened after
the original dispatch completed. It does not use heartbeat age as a stop rule
or alter finished dispatch history. `managed_queue.attempt_schedule` now permits
six total attempts at target offsets 0, 2, 4, 6, 24 and 28 hours, with minimum
spacing after completion. See the shared retry policy for late-run behavior.

`hermes_gmail.mailbox_handoff` now describes either the existing Gmail wrapper or
the selected Himalaya account. It does not itself authenticate/fetch mail or claim
SMS support. `workspace_linux` provides Linux process-group supervision and private
socket/profile inspection; Windows Job Objects remain unchanged. See
[Queue and VM runbook](QUEUE_AND_VM_RUNBOOK.md) for exact boundaries and rollout.


## Managed Greenhouse batch operation

`greenhouse_advance` accepts `seconds` (default 60, up to the existing 120-second
call range) and a grouped `answers` plan. Each plan item binds a current `ref`
and exact `managed_questions.question_key` to `answer` and its approved `basis`.
It uses the current authoritative ownership/identity gate, including accepted
employer handoffs, then one action lock for native residual work. Heartbeat and
current document/writer observations continue within that lock without nested
managed browser actions. Call expiry yields resumable continuation.

Readiness is native interactive form/contact controls with three equal structural
inventories 200ms apart. DOM receipts count actual Simplify dispatch, uncertain
work and settlement; they contain no candidate values. An actual document reload
starts a new cycle; changing fields or replacing the extension panel does not.
Without observed start/change, settlement allows five seconds for delayed work.
Otherwise three fresh stable native observations permit immediate continuation.
The second automatic pass requires actual required residuals and precedes custom
corrections. It is scheduling policy, not a manual/user retry prohibition.

Shared `form_action` uses focused search and trusted CDP insert_text fallback,
widget-associated options, exact selected-label/value readback, and field-native
validation. FramePage validates before forwarding input to the root. Unknown
questions return together; failures remain distinct. Field-context/verified events
are emitted under the batch; only verified approved answers enter the restorable
private journal. Existing salary/privacy policy, selected Resume/CV error recovery,
credentials/mail flow and submission.submit retain their ownership of those tasks.
Missing-email reload recovery remains in the same attempt, followed immediately
by this runner with fresh refs. No external handler or dependency is imported.

## iCIMS and shared post-autofill audit

`browser(method="audit")` projects the existing shared form inventory into missing
required fields, invalid values, private credential tasks, optional-blank counts,
advisory Simplify review matches, document coverage and the observed stage action.
It reads live properties without focusing or validating controls. Passwords and
verification codes expose presence only. It does not grant writer permission.
Native radio groups are scoped to their document/root/form; required native
checkboxes remain independent. Open shadow controls use exact-node action refs;
opaque widgets and unresolved frames are explicit recovery handoffs.

The iCIMS native operation, portable `application_runtime call <session-id>
icims_advance --parameters '{"seconds":60}'`, workspace host and startup brief
all reach `icims_fast.advance`. That thin runner uses the existing private filler,
selected assets, answer policy, grouped repair and submission service. It ignores
empty optional fields and treats Simplify's review list as advisory. A profile
heading plus Submit Profile identifies an intermediate action; acceptance of the
profile does not create final submission intent or mark an application applied.
Unknown screening answers are returned together, never defaulted to No.

Generic Simplify receipts retain pending writer provenance across SPA changes.
Completion evidence can settle a writer; an unrelated unknown panel fragment
cannot override it. Active/pending writers still prevent concurrent writes.
Actual document replacement invalidates its old receipt; a changed heading or URL
alone does not. Ambiguity returns audit plus scoped screenshot/Stop recovery, not
an indefinite sequence of bare observations. Existing Workday and Greenhouse
receipt/runner paths remain specialized; LinkedIn keeps its modal runner.

Synthetic regression/dispatch evidence lives in `test_form_audit.py`,
`test_icims_fast.py` and `test_icims_reconciliation.py`. The Cotiviti-shaped
fixture contains 13 optional blanks and two missing passwords. The actual native
and CLI dispatch chain reaches screening with one private credential call, one
profile click, zero ordinary field repairs and zero repeat autofill. Two explicit
synthetic screening answers then reach the existing review/submit service.
Manual completion retains user-reported evidence, requires the existing stop
lifecycle, and settles only matching queued duplicates inside that transaction.
Concurrent queue take, newer attempts and dispatched rows have regressions.

Timing tests compare the real reader with baseline `8c569656` using three runs at
100/500/1000 controls. The first passing run measured median DOM time of
23.7/545.9/3120.0 ms before and 2.1/8.2/25.3 ms after. Selector calls fell from
107/507/1007 to 5 at each size (one full-root collection). Timings vary by machine;
they are evidence, not execution limits. Sanitized traces, JUnit, later timing
runs and deployment source-hash manifests stay in the ignored private artifacts
area. The standard full managed suite also exercises the specialized portals.

These tests use disposable local state and do not submit to an employer. The
reader cannot prove the contents of arbitrary closed shadow roots, canvas widgets
or unaccepted frames, nor infer requirements enforced only by a future server
response. Those cases return specific evidence for executor recovery in the same
session. An old in-memory native schema can use the portable call above without
restarting unrelated conversations. No new service, dependency installation,
application-failure condition or retry limit is introduced.

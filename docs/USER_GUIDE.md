# Dashboard user guide

[Documentation index](README.md) · [Getting started](GETTING_STARTED.md) · [Operations](OPERATIONS.md)

The **Jobot** dashboard reads and changes the
selected managed instance. Six pages are in the main navigation; three more are
under **Advanced**. The instance identity is also under Advanced. Desktop navigation
stays in the left sidebar; on smaller screens it wraps above the current page.
The dark workspace supports keyboard focus indicators, a skip link and reduced motion.

## Page map

| Page | Use it for |
|---|---|
| [Applications](#applications) | Add, find, prioritize and control jobs |
| [Needs your answer](#needs-your-answer) | Answer unresolved application questions and prepare retries |
| [Learned answers](#learned-answers) | Inspect and maintain reusable candidate knowledge |
| [Activity](#activity) | Compare recorded outcomes and inspect attempt evidence |
| [Profile](#profile) | Maintain candidate facts and register resumes |
| [Settings](#settings) | Choose execution model, concurrency, deadline and discovery settings |
| [Accounts & history](#accounts--history) | Inspect candidate-scoped portal accounts and run history |
| [Lessons & helpers](#lessons--helpers) | Review procedural observations and registered helper versions |
| [Document records](#document-records) | Inspect document versions, selections, uploads and match assessments |

## Header and connection state

The header shows the connected mode and **Pause Jobot / Resume Jobot**. The
standard local dashboard connects automatically; **Reconnect** retries that
connection. **Refresh** requests a fresh view. Visible pages update periodically;
hidden browser tabs stop polling until visible again.

**Pause Jobot** is a persistent pause on new queued applications and discovery.
Admitted work continues, with **Finishing current work** shown until it drains.
Then the status becomes **Paused**. Requests made while paused remain saved and
wait for Resume. Resume retains the previous automatic pickup setting, history
and retry schedule.

This global control differs from a single application's Pause/Stop and from
disabling automatic pickup. It does not stop unrelated model activity or an
independently started application outside the queue.

## Applications

### Queue overview and application options

The overview shows unfinished jobs, recorded submissions, jobs needing attention
and queue state. Click a count to apply its corresponding table filter. These
counts cover the whole saved job list; **Activity** provides date-based metrics.
Expand **Queue controls & schedule** for worker status, active capacity, application
scheduling, discovery state and queue controls. A reachable dashboard with an offline worker can
save requests but cannot dispatch them until the worker returns.

During desktop startup, the worker can be online while the card says **Waiting
for Hermes to finish starting** or **Waiting for the application browser to become
available**. Jobs stay queued and begin automatically when those components are
ready. This wait does not consume an attempt or any application time limit. A
persistent message calls for checking the desktop/browser services in
[Operations](OPERATIONS.md#desktop-startup-ordering), rather than repeatedly
clicking Apply now.

The dashboard does not need to stay open for applications to run. On the Ubuntu
desktop installation, the browser service reopens the configured Brave profile
if the whole browser closes. It works independently of the dashboard and answer
entry; use **Pause Jobot** when you want to pause new application launches.

Expand **Candidate, resume and application options** to inspect the candidate,
active resume, browser profile, model/effort, submission mode and browser mode.
**Review only** records readiness for review instead of submitting. **Submit when
complete** permits the executor to submit within the configured application
workflow. Changes are for new work; existing attempts retain their snapshots.

| Action | Effect |
|---|---|
| **Queue selected** | Save/prioritize the selected jobs in the displayed sort order and request execution without waiting for the automatic schedule |
| **Apply now** on a job | Prioritize that specific job, including bypassing a scheduled retry wait; it waits for available capacity and earlier manual requests |
| **Wake existing queue** | Wake the worker for existing ready work; it does not choose the selected table row or accelerate a future retry by itself |
| **Enable automatic queue** / its pause counterpart | Enable or pause automatic pickup; explicit manual requests can still run unless global Pause Jobot is active |

The configured concurrency determines how many applications can run. Manual
priority does not evict an application already running. Repeated authenticated
delivery of the same UI request keeps its request identity.

### Jobs table

Use text search and the **Show** filter: **Unfinished**, **Needs attention**,
**Submitted**, **Canceled** or **All jobs**. Additional filters cover source,
country, assessment and added-date range under **More filters**. Clear filters restores the broad view.
The compact table shows job number, company/role, status, added date, last
disposition and time to apply. **Show all columns** reveals assessment, country,
posted date and source details; the table scrolls horizontally on narrow screens.
All columns remain sortable when visible.

Use **+ Add a job** to open the posting form. Closing the dialog keeps its draft;
a successful save clears it and refreshes the pipeline. Saving a job uses the
existing queue settings; it does not change submission permissions.

The permanent **#** is assigned when first added. Rediscovery does not change that
number or the added date. Sortable columns include company/role, status,
assessment, country, original posted date, source/reference, added date and last
disposition. Missing posting metadata is shown as unavailable rather than guessed.
Source references help trace a posting back to discovery or external intake.

Job rows can also show **Matching posting** or **Possible duplicate** with the
other job's number and the matching evidence. **These are different jobs**
dismisses that pair; **Reconsider match** restores automatic matching. Original
jobs and attempts remain visible. Dismissal does not queue work automatically.
In Settings, **Duplicate jobs** offers **Off**, **Show matches only**, and
**Skip applied or canceled duplicates**. The last option skips new work when a
high-confidence matched posting has this candidate's recorded success or an
explicit **Canceled** disposition, including a "no longer interested" reason.
Restoring the original canceled posting removes that exclusion; dismissing an
incorrect pair removes matching-based exclusion. Earlier failures still follow
the existing retry schedule. Canceled matches are not reported as submissions.

The optional daily Discord summary arrives at 8:00 a.m. Central for the previous
calendar day. It separates jobs submitted, jobs attempted, total attempts,
duplicate jobs skipped, and postings reaching the six-attempt automatic limit.
It also reports the attempts used by successful jobs and attempted jobs still
without submission. See [count definitions](jobbot-v1/SUBMISSION_ALERTS.md#daily-numerical-summary).

**Select all** and the heading checkbox select unfinished jobs shown by the current
filters. Check the selection count and order before **Queue selected**. Submitted
and canceled rows are not silently selected for new applications. Clear selection
resets the selection. Canceled views provide their own selection/restoration controls.

Expand a job for attempt details, failure/recovery information and current
application controls. Technical diagnostics are collapsed so normal queue work
does not require reading runtime identifiers.

### Add, edit, cancel and restore

**Add a job** accepts an official URL and optional company/title. Active intake
can enter the automatic queue; adding a job is not necessarily a passive bookmark.
The existing eligibility, success, cancellation and answer-handling policies apply.

**Edit job URL** corrects the posting link while preserving its number, added date,
history and source references. Saving does not navigate an already open application.

**Cancel selected** records an operator disposition and reason, such as Posting
closed, No longer interested or Manually applied. It preserves attempts and portal
accounts. **Restore selected** makes canceled jobs available again without erasing
the cancellation history. “Manually applied” is an operator disposition; it does
not manufacture an automated submission event.

### Retries and current applications

Automatic recovery has six total attempts in a series, targeting elapsed offsets
of 0, 2, 4, 6, 24 and 28 hours from the first start. Each retry also waits at least
two hours after the preceding completion, or four hours for the sixth attempt.
Busy capacity or a long application moves the due time later. Other ready jobs can
run while a retry waits.

After an unsuccessful series the job remains **Needs attention** with its reason.
An explicit retry request can start another series; failed or uncertain history
is not a permanent ban. Recorded success, explicit cancellation, review-only
completion, user stop and pending required answers retain their distinct handling.
See the authoritative [retry policy](jobbot-v1/RETRY_POLICY.md).

Individual application controls act on that owned session. Pause allows operator
intervention through its existing lifecycle; Stop requests cleanup of its owned
executor/targets; Restart replaces its application target for recovery. Restart
does not clear the attempt's evidence or reset its original deadline. Personal
browser tabs and unrelated applications remain outside those controls.

## Needs your answer

This is the actionable inbox for unresolved application questions. It groups
repeated questions while keeping company, role and affected applications visible.
The inbox opens in bulk mode so you can edit up to 12 questions together. Each row
shows the company and position, its matching applications, and a control to apply the reply
to all shown matches or one position. **Save N drafts** saves populated drafts
across pages and search results, including drafts entered in the focused editor.
Blank questions are left unanswered. The receipt reports saved questions and
distinct applications; **View AI learning** opens extraction activity.
Choose **Focus on one question** for the individual editor and mobile picker;
**Answer in bulk** returns to the batch view without losing drafts.

Drafts survive polling, searches and switching views within this page, but are not
stored across a browser reload. Failed saves keep remaining drafts. Large batches
are saved in groups of at most 100 application replies; if a later group fails,
the page reports the saved portion and retains the remainder for review.

1. Check which applications the selected question belongs to.
2. Supply the response that is true for those applications, using the offered
   choices when the employer constrains the answer.
3. Use **Save N drafts**, or **Save answer** in focused mode. Responses are recorded
   for the selected applications immediately; background AI learning is separate.
4. Review **Ready to retry** once all required answers for an application are saved.
   Use its **Save and queue retry** action to request another attempt.

The page has **Needs your answer**, **Ready to retry** and **Answer history** views.
History includes previous response revisions and resolved application context.
Submitted, canceled, archived, explicitly queued answer retries and fully answered
applications with a live browser leave the
actionable inbox without being relabeled as answered when they were not answered.
Live applications can consume saved answers in their existing session. They do
not appear as ready for another retry solely because all questions were answered.

Search, pagination and a focused detail pane keep the list manageable. Selection
and draft answers survive polling and reorderings. Saving one response can move
to the next question without discarding other drafts.

**Save answer** does not require making a universal reusable answer.
**Add reusable answer** is an optional separate action. If a question changes on
the employer form, review its current wording/choices rather than assuming the old
response still maps to it. Answered retries use the normal queue and pause policy.

## Learned answers

Use `{company}` in a question or alternate wording for an explicitly shared answer,
such as “Do you own stock in {company}?” → “No”. Choose **All matching applications**
for the default; save **This company** or **This application** for exceptions, which
take precedence. A reply about one employer alone is not a fact about every employer.

Each answer shows matched-question and recorded-form-use counts, applications
covered, last use, and up to 20 recent evidence records with company, position,
original question and answer version. Matches were selected for saved questions;
form uses come from private application journals. Neither proves submission.
Agent use without recorded provenance is not counted, so old evidence can undercount.
The overview counts reusable answers, distinct applications with recorded reuse,
matched questions and recorded form uses across profiles. **Which applications
used these answers?** lists the 20 most recently recorded applications. An
application using several answers is counted once in the overview.

This page holds current reusable knowledge and its source history. The views are
**Current**, **Retired** and **Learning activity**. Search by question, answer,
company or position; select one entry for its details and original responses.
Learning activity includes successful extraction with **View learned answer**,
pending work, application-specific responses, conflicts and failures. It shows
the latest 100 records and the full record count, so search here is limited to
those recent records. Current reusable answers remain searchable in **Current**.
Activity details show attempts, update time and scheduled retry time where
available. A conflict shows the current and proposed answers before editing.

AI learning extracts generalized, grounded answers from application responses.
Human saves do not wait for inference. A learning error leaves the original answer
saved and retries independently. **Run AI learning** requests another learning
pass; **Check unanswered questions** reevaluates pending requests against available
knowledge. Neither button starts an application executor.

When new wording expresses the same fact as an existing answer, learning keeps
the current answer and adds the source and equivalent question wording. It checks
meaning in the context of both questions, scope and conditions, with exact evidence
from the existing answer. Different amounts, currencies, pay periods, qualifiers
or scope still need review. Uncertain comparisons remain visible as conflicts;
the model cannot replace your current answer merely by calling it equivalent.

Use **Add reusable answer** for explicit knowledge you want to maintain yourself.
An entry includes:

- The selected candidate, general question and current answer.
- Other question wording it covers.
- Scope: all matching applications, a company, or a single application.
- Optional country, currency and compensation period.

Edit knowledge when circumstances change. Retire an answer to stop future reuse
while preserving earlier versions; restoration is explicit. Entries indicate AI
derivation or **Added by you** provenance. Conflicts and scope differences should
be resolved using the actual facts, not by treating the most frequent old response
as correct. A company-specific response is not automatically universal.

See [Data model](DATA_MODEL.md) for how human response history, profile facts,
library revisions and learning work records fit together.

## Activity

**Application results** supports Today, Last 7 days, Last 30 days, Lifetime and
custom dates. Calendar boundaries use the configured reporting timezone. The 7-
and 30-day ranges include today.

Metrics group attempts by their **start date**, including retries and jobs later
canceled or archived. Distinct postings and new submissions are separated from
raw recorded counts and already-applied outcomes. Queue dispatches have their own
start-date cohort. A job-level submission rate is not the same as an attempt rate.

**Current applications** shows active sessions and progress. **Attempt history**
lists attempts in the selected period; select one to open its evidence and timeline
under **Attempt details**. The timeline distinguishes stages, actions, waits and
recorded outcomes. It is the place to inspect the actual reason a run ended.
Failure summaries prefer the specific final obstacle recorded for the attempt.
Earlier helper errors remain in the timeline; an explicit later outcome can
refine the summary without rewriting the original attempt.

**Advanced run controls & diagnostics** exposes run selection, Request pause,
Resume, Request stop, ownership details, targets and legacy budget-extension
records. These protocol diagnostics are distinct from the main queue controls.

Use the evidence source in the attempt report when describing a success. A Submit
click, helper return status or executor exit code does not independently establish
employer acceptance. See [Activity statistics](jobbot-v1/ACTIVITY_STATS.md).

## Profile

Select the candidate and edit **Screening & background**, **Employment & outside
activities**, **Work authorization**, **Work preferences & availability**,
**Compensation preferences**, and **Communication & verification**. Additional
immigration and government/licensing questions are in optional expandable sections.
Each section shows how many answers are populated. Yes/no controls distinguish
**Not answered**, **Yes**, and **No**; an unset value never supplies a personal default.
Background-check consent, drug-test consent, felony convictions, other criminal
convictions, and arrests are separate facts. Question-specific definitions and
exceptions remain relevant when an employer asks different wording.

**Suggestions from saved answers** shows compatible general learned answers and
explicit saved responses, their source question/date, the current profile value,
and any conflicting responses. **Use saved answer** adds the chosen value to the
draft. **Save profile** persists the draft and source revision. Company/job-scoped
answers and mismatched country qualifiers are not promoted by this action. Editing
a field directly records it as a profile edit; the original learned entry and
answer history remain intact.

**Advanced Factual JSON** edits the same draft and preserves additional candidate
facts, without account passwords or other secrets. Polling does not replace unsaved
edits or their original revision; unchanged refreshes preserve focus and open
suggestions. **Reload saved profile** discards the current draft. A conflicting
save leaves the draft visible.
Save changes the current candidate and reconciles eligible pending questions;
new attempts use the updated profile. Existing attempt snapshots and explicit
application-specific human responses retain their recorded values.

The profile is stored in the managed database. When the installation configures
`profile_export_path` for its selected candidate, saving or importing also updates
that private JSON file. The page reports whether it is synced and offers **Sync
saved profile to JSON** after an export failure. A file-write failure does not undo
the database save or stop applications. The export preserves account credentials,
password overrides, policy configuration, and legacy resume text. Editing an
exported file outside Jobot does not silently import its values into the database.

**Experience & application answers** connects the selected profile to its reusable
knowledge. **View this profile’s learned answers** opens that candidate’s answers;
**Add experience or preference** adds a sourced, scoped reusable answer without
duplicating it into the factual JSON. Existing entries remain editable in Learned
answers, with earlier versions and application evidence retained. Employer/job
exceptions take precedence over a matching general profile answer. For recognized
structured questions, the current profile takes precedence over general learned
answers; explicit human responses to the actual application take precedence over
both. Unrecognized or more qualified wording returns to ordinary executor handling.

**Import & Resume Assets** can import factual data from a legacy JSON file. It
excludes credentials, secrets and policy fields from that factual import and
reports skipped content. Approved private policy configuration is a separate path.

**Upload & register resume** stores the file locally, computes SHA-256 and records
a versioned resume asset. Registration does not upload to an employer. Confirm the
intended active resume in application options before requesting new work.
The upload endpoint accepts PDF, DOCX, DOC, TXT and RTF files, up to 10 MiB.

## Settings

**Application model** selects the executor/provider, model and supported effort.
**Refresh models** refreshes the installed catalog. Save before requesting new
work; running applications keep their selected model.

**Discovery model** defaults to **Same as application model**. Choose **Separate
model** to select a different provider, model and reasoning effort for job search.
The shared choice follows later application-model changes automatically. Discovery
keeps its own tools and profile, while receiving the selected model explicitly.

**Answer learning model** has the same choices and default. It controls both
generalizing saved responses and matching reusable answers to new questions.
The displayed summaries identify the selected provider/model. Save settings to
apply changes to the next discovery run or learning call; existing work continues.

**Simultaneous applications** selects 1–5, default 1. Existing browser mode uses
separate application windows in the retained profile. Lowering capacity allows
current applications to finish. Shared logins still behave like multiple manual
windows on the same employer site.

**Application time limit** defaults to 30 minutes. Set 1–1440 minutes or uncheck
the option for **Off**. It includes model calls and recovery and excludes waiting
in queue. At expiry, supervision stops the owned executor and completes cleanup.
Changes apply to new attempts. Reloads and same-dispatch replacement do not restart
the clock.

**Job discovery** configures the desired job limit and interval for later discovery
runs. **All Operational Settings** shows the remaining settings. **Health & Resolved
System Paths** is useful for checking instance/configuration during troubleshooting;
its machine-specific output should stay private.

[Configuration](CONFIGURATION.md) lists defaults, precedence and legacy fields.

## Accounts & history

Under **Advanced**, **Portal Accounts** shows namespace, candidate identity,
account status, last confirmation and password source. An unsuccessful application
does not erase confirmed account state. Saved passwords and verification codes
are not displayed.

Use **Search portals** to filter the list instantly by site name, address or
account email. Search ignores case and surrounding spaces; the count shows
matching accounts out of the total. The filter stays in place during automatic
refreshes. **Clear search** restores the full list. Run history is not filtered.

Choose **Set password override** on a tracked account to enter and confirm a
portal-specific password. **Update override** replaces it; **Remove override**
restores the previously configured credential (usually the default). The override
applies only to that candidate, account email and verified portal namespace.
Saving in Jobot does **not** change or reset a password on the employer website.
For an existing account, enter its actual password; for registration, enter the
password Jobot should use to create it. Site length and character requirements
still apply. Jobot does not automatically generate or reset passwords here.

Changes take effect on the next private credential fill, including a later fill
in an open session; fields already filled are not changed by saving. The default
password, factual profile and application history are preserved. The editor is
available for tracked accounts with resolved candidate/portal identity and a
configured readable private credential file. Legacy unresolved accounts show an
explanation instead. This first version does not add accounts before a portal is
tracked, and does not integrate a password manager.

**Run History** provides historical managed run context. This page helps explain
account reuse; it does not make all sites belonging to one ATS share an account.
See [Data model](DATA_MODEL.md).

## Lessons & helpers

**Observed Lessons** holds procedural observations from execution. Candidate
observations are advisory; an operator can deliberately activate verified lessons.
These are procedure records, separate from candidate facts in Learned answers.

**Versioned Helper Catalogue** records existing helper implementations, hashes,
scope, tests and status. **Register an Existing Helper** needs an approved file,
version, capability, SHA-256 and test references. It does not write a new helper or
silently install generated code. Activation follows the existing evidence and
quiescent-ownership rules. This page is primarily for maintainers.

The canonical [helper/caller map](jobbot-v1/APPLICATION_RUNTIME.md) explains each
helper's implementation responsibility.

## Document records

**Document Versions** separates a document being available, selected, upload
attempted and upload confirmed. These stages are not interchangeable.

**External Match Assessments** records evaluator outputs with document/profile
versions and provenance. A score is the evaluator's assessment, not a hiring
probability or a guarantee of eligibility.

**Register External Document Metadata** registers a resume or cover-letter version
with storage reference, SHA-256 and source. **Select a Document** associates an
available version with a job. The normal resume upload workflow is in Profile.
The application does not generate cover letters automatically.

## Common questions

| Observation | What to check |
|---|---|
| Job is saved but nothing starts | Global pause, worker status, automatic pickup setting, selected capacity and retry due time |
| Expected history is missing | Instance identity and configured database; check that the legacy server was not launched |
| Retry waits despite Wake existing queue | Due time and earlier manual work; Apply now targets one job explicitly |
| Answers saved but learning still pending | Original answers are already durable; inspect Learning activity and dashboard learner availability |
| Running application still uses old settings | Its immutable snapshot; settings changes apply to new work |
| Result says interrupted after the limit | Read the distinct timeout reason and any preserved submission evidence |

For process-level checks and recovery, see [Operations](OPERATIONS.md).

# Research handoff: restrictions that interrupt application submission

Repository: https://github.com/rejozmathew/jobot

Branch: `codex/runtime-simplification`

Date: September 9, 2026. Resolve and record the branch HEAD before auditing.
This document is a starting point, not a claim that every restriction is removed.

Later September 9 follow-up: email selection now belongs entirely to the LLM
using Hermes Gmail. The `email_code` delivery-label veto and Jobot's automatic
mailbox verifier were deleted. The executor chooses the relevant message closest
to the request timestamp and supplies its code to normal browser fill or the
grouped field helper. The user also explicitly requires approval before any new
execution restriction or refusal condition is added; this is recorded in AGENTS.md.

## Problem and desired behavior

The product should complete the user's authorized job application. Helpers are
there to perform routine work and expose useful evidence. Too often, a helper's
limited recognition, uncertain click, stale state, elapsed time or ownership
bookkeeping becomes an application-wide veto. Another layer then refuses the
very operation needed to recover. The executor loses the ability to reason and
continue even when the employer page still offers a straightforward next step.

The latest motivating incident was an employer form requiring an email code
after Submit. The application was unfinished, but click history set
`submission_pending`; form/credential/recovery paths interpreted it as read-only.
A special rejection-proof protocol was then required to clear that restriction.
This was a general workflow design problem, not a reason for a Philo exception.
The retained screenshot also showed another unanswered question explicitly
described as optional; do not turn that question into a claimed employer requirement.

The user explicitly accepts independent browsers working on the same job or
account. Do not justify exclusive posting/account ownership with speculative
duplicate risk. Confirmed success, candidate correctness, real employer behavior,
explicit user instructions and the practical behavior of a physical browser are
different concerns that need concrete analysis.

## Concrete changes already made

These are verifiable examples for the audit, not an exhaustive current catalog.
Use Git history to see the removed conditions and trace all surviving callers.

| Removed or relaxed restriction | Implemented behavior and source |
| --- | --- |
| A page-label classification or programmatic email verifier refuses an executor-selected code | Removed `verification_delivery_unconfirmed`, automatic Gmail lookup and sender/company/template/timestamp/ambiguity filtering from code entry. Hermes reads mail; the LLM selects; the browser enters the supplied code. `managed_credentials.py`, `hermes_gmail.py`, `browser_helpers/form_controls.js`. |
| Prior failed/interrupted/unknown attempt requires non-submission reconciliation before retry | A new request starts another attempt unless success is recorded. Historical evidence is preserved. `managed.py`, `application_runtime.py`, `managed_questions.py`, `static/jobbot.js`; checkpoint `0383482`. |
| A Submit click permanently disables fields, answers, credentials and recovery | Removed `submission_pending_read_only` conditions from browser, host, answer and reload paths. `application_runtime.py`, `workspace_host.py`, `managed_events.py`, `managed_questions.py`. |
| Only a specially scoped rejection proof permits another Submit | Shared `submission.py` reports ordinary `application_incomplete` work and allows another explicit current-control submission. It checks delayed confirmation first. The compatibility rejection endpoint is no longer a prerequisite. |
| Workday always enters confirmation-only mode after any Submit intent | Removed the unconditional early branch and post-click browser-recovery exclusions in `workday_fast.py`; another advance follows the current page. |
| An old target ID prevents submission observation after browser restart | Earlier evidence is retained while the shared collector observes the replacement target in the same application session. `submission.py`. |
| Legacy Hermes bypasses every form operation after its first Submit | Removed the global `submit_clicked` short circuit and per-submit permanent refusal in `managed_hermes_worker.py`. |
| Mandatory internal resume-upload receipt even if Simplify already supplied the file | Removed the older Hermes worker's `resume_uploaded` submission gate and unconditional re-upload instruction. Missing or wrong attachments still have the ordinary upload operation. |
| One active session/attempt owns a posting globally | Removed `Service._assert_no_owner`, reservation exclusion and migration-level `uq_managed_active_job` / `one_local_job` indexes. Distinct requests can use distinct configured workspaces. `managed.py`, `managed_sessions.py`, migration 17. |
| Starting another request automatically stops an earlier same-job request | Ordinary start allocates independently; explicit retry replaces only its named session. `application_runtime.py`. |
| One browser exclusively owns a candidate's portal account | `coordinate_account` returns the namespace without the `account_in_use` veto. Candidate/credential association remains separate. `managed_sessions.py`. |
| A busy host rejects the next operation after five seconds | The host queues operations on its physical browser. `workspace_host.py`. |
| Pending click prevents pause, resume or same-attempt restart | Removed submission-state conditions from session pause/attach/connect and host restart. Actual browser lifecycle remains visible. `managed_sessions.py`, `workspace_host.py`. |
| URL title/location/locale spelling vetoes the same Workday requisition | Shared job identity uses employer/site/full requisition; owned inspection and recovery remain available. `managed_identity.py`, `application_runtime.py`; checkpoint `5afb206`. |
| Helper time slice, unfamiliar controls or missing Simplify ends the application | Helpers hand current evidence to the executor; loading and browser recovery continue in the same session. Shared controls, runtime, host and canonical skills; checkpoints `5afb206` and `68a7865`. |
| Unknown Simplify state forbids cancelling a broken document | Shared reload/restart can recover a broken page; new observations govern subsequent work. `managed_events.py`, `application_runtime.py`, `browser_controls.py`; checkpoint `68a7865`. |
| Incidental timing/decision counters veto otherwise useful local work | Local semantic timing became telemetry; the global two-non-dispatch auth cap and one-action-per-screen restriction were removed. See `5afb206` and the historical stop-condition audit for exact affected symbols. Action-specific authentication restrictions still warrant review. |
| Missing post-click evidence triggers an unrelated two-minute inspection shutdown | Removed that automatic closure; explicit Stop and configured maximum runtime remain separate. See `5afb206`. |
| Optional answer journaling/progress failure aborts form recovery | Best-effort diagnostic failures no longer disguise an executed write or stop recovery. `application_answers.py`, runtime/Workday callers; see `5afb206` and subsequent history. |

Related correctness changes: concurrent attempt completion preserves successful
posting status, and structured dispatch/document/frame IDs are no longer damaged
by prose redaction of numeric UUID segments. Neither is a new execution veto.

## Copyable research assignment

Perform a deep, source-based audit of the entire repository above at the named
branch. Your objective is to find every condition that can prevent, defer,
abort, freeze, disable, redirect or prematurely finish an authorized application.
Evaluate each condition from first principles against actual submission progress.
Do not assume an existing guard is necessary because of its name, documentation
or a test asserting rejection. Prefer deleting unnecessary restrictions to
inventing exceptions, approval layers, policy frameworks or more status machines.

Read `AGENTS.md`, both canonical application skills, `APPLICATION_RUNTIME.md`,
`RETRY_POLICY.md`, this handoff, and the historical `STOP_CONDITION_AUDIT.md` and
its catalog. Historical documents are evidence of earlier behavior; verify
current code and callers independently. Do not limit the investigation to these
documents or the files listed above.

Trace every execution entry point: local CLI/runtime, native Hermes plugin,
Workday runner/auth helpers, generic and embedded browser controls, Simplify,
credentials and mailbox verification, service methods, host/process lifecycle,
legacy HTTP/worker adapters, dashboard/answer queue and database constraints.
Follow indirect checks and translated errors across layers, including success
signals, stale checkpoints, policy defaults, retries, user-input routing, budgets,
timeouts, URL identity, action receipts, locks, leases, account states and finish
cleanup. Include disabled UI controls, swallowed errors, early returns and
instructions that make an executor stop despite available operations.

Build a complete, deduplicated inventory. For each restriction provide exact
file/line and symbol references, callers, triggering condition, affected scope
(one operation, browser, attempt, job, account or whole run), persistence/reset
behavior, executor-visible response and available recovery. Explain the concrete
harm it prevents, whether available evidence establishes that harm, whether
another existing check already handles it, and an example of legitimate progress
it can wrongly block. Separate demonstrated incidents from inferred risks and
unverified hypotheses. Do not infer causation from outcome counts alone.

For each item recommend **remove**, **replace with observation/advice**, **queue
internally**, **narrow to the actual affected operation**, or **retain with a
concrete justification**. Explicitly identify recovery deadlocks where the veto
also blocks the next corrective action. Inspect remaining account-creation and
sign-in uncertainty, writer-state checks, stale-owner/fence rules, profile locks,
semantic budgets, adapters' telemetry failure behavior, confirmation detection,
and duplicate suppression without presuming any deserves exemption.

Model representative flows from request through confirmation: first attempt,
retry after failure, inconclusive Submit followed by email verification, invalid
code followed by correction, broken page after a click, two sessions on one job,
two sessions using one account, helper timeout followed by manual recovery,
late confirmation and competing attempt outcomes. Show where the executor still
has useful work and where the implementation prevents it. Check for caller or
documentation contradictions that could restore removed behavior.

Deliver a concise executive diagnosis, the exhaustive inventory with coverage
method and counts, a ranked removal/simplification plan, concrete before/after
flow examples, and a short justified list of remaining boundaries. Include the
branch and exact audited commit, distinguish local from legacy behavior, and
call out uncertainty. Propose validation for the highest-risk changes without
adding or running tests in this audit. This assignment is research only: no
source changes, live applications, production data edits or publishing. Do not
claim completeness from a keyword scan alone.

## Verification and deployment limits

The latest user instruction explicitly forbids new tests and regression runs.
The current continuation changes received source/diff and syntax review only;
existing contradictory test assertions were removed or aligned, with no new
cases. Earlier suite totals belong to earlier commits and cannot validate HEAD.
No live employer form was used as an engineering fixture. The requested record
correction and dashboard restoration were separate operational actions.

Current CLI invocations load current source. Existing native/host processes keep
their imports until their normal lifecycle replaces or reloads them. Physical
profile allocation, target/candidate association, actual writer-state checks,
account recovery rules and legacy lease behavior remain substantive audit areas.
Their presence here is not a blanket defense of them.

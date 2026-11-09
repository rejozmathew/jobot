# Cross-source duplicate matching

## Company/title matching — October 8, 2026

The operator approved an additional local matching layer for postings whose
successful history or explicit operator cancellation is hidden behind different discovery URLs. Failed, blocked,
interrupted and uncertain attempts remain retryable under the existing policy.
`duplicate_matching_mode` defaults to `shadow` (show matches only). `enforce`
suppresses a new admission only when a high-confidence match has recorded success
for the selected candidate or an explicit **Canceled** disposition, including
"no longer interested." Cancellation remains a posting-level operator choice;
failed attempts and stopped/canceled attempt outcomes do not set it automatically.
`off` disables this additional layer; established
URL-identity success/cancellation handling still applies.

`job_duplicates.py` normalizes company legal suffixes, punctuation and common
title abbreviations. Comparisons stay within a normalized company. Optional
LM Studio embeddings compare the remaining title variations using the model's
`clustering:` prefix. The initial title threshold is 0.975, a similarity score,
not a probability. It is versioned with the configured model and input format.

High confidence requires the same observed employer posting ID, or matching
company/title (exact or above the embedding threshold), matching seniority, and
the same location plus an identical explicit posting date or substantial
description. Different employer requisitions override text similarity. Missing
corroboration produces a possible match, not an application restriction. Source
IDs such as LinkedIn posting IDs are not treated as conflicting employer IDs.
No company names or live postings are hard-coded.

Migration 29 adds model/input-keyed embedding cache rows, pair decisions and
first duplicate-admission receipts. It does not merge/delete jobs, fabricate a
submission, copy cancellation dispositions, or insert semantic matches into URL/ownership
aliases. Pair decisions are recomputed against current metadata and stored with
input hashes and reasons. An operator can choose **These are different jobs**
on either job's match details; **Reconsider match** restores automatic matching.
Dismissal does not itself enqueue a job or erase actual submission evidence.
Restoring the original canceled posting or dismissing an incorrect match removes
matching-based cancellation exclusion; ordinary queue eligibility still applies.

The dashboard runs background embedding refreshes; configured intake also
refreshes the incoming company's matches before returning. Model calls occur
outside database transactions, with a five-second HTTP timeout. Unavailable or
invalid embeddings leave exact matching and ordinary eligibility available.
Changing the endpoint, model, revision or input format selects another cache;
vectors from different models are never compared. The current model's cached
vectors remain usable through a temporary server outage.

Queue reconciliation and admission recheck success and cancellation in their transaction. Pending
duplicates settle as `already_applied` or `canceled`, preserving the actual reason;
active dispatches are not stopped by a
background match. Requests already underway can still discover success later.
Each actually suppressed incoming job/candidate is counted once, on its first
suppression date, rather than once per worker poll. Historical matches alone do
not count as skipped applications. See [Submission alerts](SUBMISSION_ALERTS.md)
for daily counts and [Retry policy](RETRY_POLICY.md) for unchanged failed retries.

Synthetic coverage: `test_job_duplicates.py`, `test_daily_summary.py`, existing
cross-source identity/admission tests and the managed suite. Read-only evaluation
of real metadata is separate from these fixtures; a finite comparison set does
not establish perfect future matching accuracy.

## Existing URL identity

Shared intake identifies supported ATS postings independently of discovery feed,
company display name, title and mutable imported requisition labels. This applies
to every employer; there are no company names, employer domains or live job IDs
in the matching code or fixtures.

For Greenhouse, the board token plus public posting ID identify the posting.
The posting ID is distinct from the employer's `requisition_id` field. A hosted
board URL supplies both. A custom employer URL must supply a consistent `gh_jid`
and a verified namespace or a corroborating `greenhouse:board:posting` source
reference. This supports arbitrary employer URL paths and HTTP/HTTPS aliases
without inferring a board from a company name or matching a bare number across
unrelated employers. Unknown query parameters remain part of the identity.
The same intake entry point uses the existing Workday, LinkedIn and iCIMS
identity readers. A hosted Workday public posting can omit the location segment.
Its intake key still uses the same host, career site and full requisition when
the remaining role slug has an explicit Workday requisition suffix and the
canonical URL has no query parameters. The location-free spelling applies to
posting keys. Live ownership and observed redirect checks use the existing
route reader. No new network call or availability dependency is introduced.

The posting key takes precedence over rediscovered requisition labels. Incoming
conflicting labels do not create a new job, overwrite retained titles or attach
the incorrect requisition as an alias. Existing source provenance is retained.
Generic source IDs and company/title similarity alone do not merge records.
Missing or conflicting posting evidence falls back to existing URL/identity
handling; it does not create a new execution refusal.

Migration 23 adds posting aliases to existing jobs and their retained source URLs.
It preserves all job rows, attempts, source records, evidence and original keys.
Ordinary queue reconciliation removes pending work whose linked history already
records success or explicit cancellation. Active dispatches remain owned by
their existing executor. Unsuccessful and uncertain attempts remain retryable.

The helper/caller map is in [RETRY_POLICY.md](RETRY_POLICY.md). Browser navigation
scope remains separate from intake identity. This change does not read arbitrary
inbox confirmations or infer a successful application from rediscovery metadata;
the existing evidence reconciliation operation records user-provided completion.

Validation uses fictional employers and synthetic databases in
`test_cross_source_duplicates.py`, plus the existing identity, intake and queue
suites. The regression includes wrong incoming titles/requisition labels,
multiple discovery sources, different ATS URL forms, historical aliases, opaque
queries, conflicting IDs, and continued retry eligibility for uncertain history.

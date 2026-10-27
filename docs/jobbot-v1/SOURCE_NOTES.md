# Evidence and limits

## Requested basis

This specification consolidates the user's decisions in this conversation: Windows Hermes builds/tests; Ubuntu rollout later; adaptive Hermes batch continuity; Simplify-first bulk filling; multi-source queue; worker-neutral interface; reliable timing/status/control; identity-scoped portal accounts; reusable lessons/helpers; optional external assessment/document storage; and a safe fresh start rather than blind data deletion.

It is a design proposal grounded in that conversation and the reviewed repository/skill material. Proposed APIs, records, checks and stage names are not claims that they already exist.

## Reviewed repository baseline

Repository: `https://github.com/rejozmathew/jobot`

Branch: `hermes-modified`

Last reviewed commit in the conversation: `923f2576f9c059370222ef416f50f97a8cfc9f70`.

Source review in this conversation covered the API/runner, database/queue, application tracker, step tracker, workflow, registry, CDP client and tracker tests. Important checks to reproduce include internal-agent coupling, in-memory status/control, unconditional running-job cleanup, unsafe retry/start transitions, account lookup missing selected-identity filtering, and timing that depends on caller instrumentation.

The baseline requirements file used lower bounds for browser-use, FastAPI, Uvicorn, python-dotenv, Pydantic and SQLAlchemy. Establish reproducible tested dependencies rather than assuming fresh installation selects the same versions. Do not upgrade indiscriminately.

These are source-review observations, not live-runtime profiling. The current Windows checkout may have unpublished work; inspect it before editing.

## Supplied skill archive

`job apply skills.zip` contains `job-apply/` and `job-application-submit/`, including Simplify, Workday, Greenhouse, CDP and scheduled-handoff references. It does not contain `job-posting-harvest/`.

The supplied main skill includes competing normal-path and Simplify-first instructions; the old scheduled-handoff reference warns about fresh sessions, duplicate starts and timeouts while a detached process continues. These are useful consolidation targets. Claimed successful applications in skill text remain author-reported history, not independently reproduced results.

Do not distribute the original archive wholesale without reviewing personal paths/facts and instructions. Read the actual active Windows skills and compare versions.

## Official documentation consulted, 2026-09-06

- Hermes tools/toolsets: `https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/`
- Hermes skills: `https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/`
- Hermes hooks: `https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/`
- OpenAI Astra model documentation: `https://developers.openai.com/api/docs/models/gpt-6-astra`
- OpenAI Work/Codex access notes: `https://help.openai.com/en/articles/20001275/`
- SQLite online backup: `https://www.sqlite.org/backup.html`

Hermes documents terminal/file operations and agent-managed procedural skills; installed capabilities and hook signatures still must be verified. OpenAI model availability does not prove a particular third-party Hermes provider/account can use it. Verify the actual resolved model/provider and do not silently switch billing routes.

No code changes were made to the user's repository by creating this package. No Windows or Ubuntu application tests, live submissions, credential changes, database resets, or deployments were performed here.

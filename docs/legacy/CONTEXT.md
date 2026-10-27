# Jobot - Development Context

> Historical February 2026 development context. These setup instructions, models,
> support claims and architecture describe the original browser-use application.
> Start with the [current README](../../README.md), [architecture](../ARCHITECTURE.md)
> and [project history](../PROJECT_HISTORY.md) for the managed Jobot runtime.

## Project History

This project was extracted from a fork of [browser-use](https://github.com/browser-use/browser-use) to be a standalone application that uses `browser-use` as a dependency.

**Original fork**: `github.com/rejozmathew/browser-use` (branch: `job-applier`)
**Standalone repo**: `github.com/rejozmathew/jobot`

---

## Current State (as of 2026-02-03)

### What Works
- ✅ **Web dashboard** at `localhost:8000` - add jobs, run queue, view status with expandable step details
- ✅ **Job queue system** - queued → running → applied/failed/needs_review
- ✅ **SQLite database** - persistent storage with step tracking capability
- ✅ **Profile-based form filling** - loads user data from `profile.json`
- ✅ **Multi-step form handling** - successfully completed TCW (iCIMS), Workday applications
- ✅ **GIF recordings** - saves recording of each application attempt
- ✅ **Local LLM support** - optimized for `qwen3-vl-8b` via LM Studio
- ✅ **Migration support** - seamless upgrade from JSON to SQLite
- ✅ **Programmatic navigation** - navigates to job URL before LLM starts (saves LLM calls)
- ✅ **Resume-first strategy** - uploads resume first to leverage auto-fill

### Configuration
```env
OPENAI_API_BASE=http://192.168.1.27:1234/v1
OPENAI_API_KEY=local
OPENAI_MODEL=qwen/qwen3-vl-8b
JOB_APPLIER_DB_PATH=./job_applier.db
JOB_APPLIER_MAX_STEPS=100
JOB_APPLIER_MAX_HISTORY=10
```

### Tested Platforms
- ✅ TCW (iCIMS) - **Successfully submitted** (62 steps, 2026-02-03)
- ✅ Alvarez & Marsal (Workday) - **Successfully submitted** (170 steps)
- ✅ SuccessFactors
- ✅ CBOE Careers

---

## Optimizations Already Implemented

### 1. Programmatic Navigation (NEW - 2026-02-03)
- **Problem**: Agent wasted LLM calls deciding to navigate
- **Solution**: Use `initial_actions` parameter to navigate and wait before LLM starts
- **File**: `job_applier/agent.py` (lines 210-220)

### 2. Resume-First Strategy (NEW - 2026-02-03)
- **Problem**: Manual form filling when resume auto-fill could populate fields
- **Solution**: Instructions emphasize "UPLOAD RESUME FIRST" then check for pre-filled fields
- **File**: `instructions.md`

### 3. Built-in browser-use Actions (UPDATED - 2026-02-03)
- **Problem**: Custom element handlers used deprecated API methods
- **Solution**: Use browser-use built-in actions which are well-tested:
  - `upload_file`: Smart file input detection with fallbacks
  - `select_dropdown`: Handles `<select>` elements
  - `input`: Text input with autocomplete detection
- **File**: `job_applier/element_handlers.py` (simplified wrapper)

### 4. Context Window Management
- **Problem**: LLM context overflowed during long applications
- **Solution**: `max_history_items=10` keeps only recent 10 steps in context
- **File**: `job_applier/agent.py`

### 5. Screenshot Size Reduction
- **Problem**: Vision tokens were too high
- **Solution**: `llm_screenshot_size=(800, 600)` reduces token usage
- **File**: `job_applier/agent.py`

### 6. Shorter Instructions
- **Problem**: Base prompt was ~5000 bytes
- **Solution**: Rewrote `instructions.md` to ~2400 bytes with focused directives
- **Key changes**: "Navigate FIRST", "Batch fill", "Keep thinking SHORT"

### 7. Success Detection Fix
- **Problem**: Agent saying "cannot complete" was marked as "applied"
- **Solution**: Check for failure phrases BEFORE success phrases
- **File**: `job_applier/agent.py`

### 8. Expandable UI with Step Details (NEW - 2026-02-03)
- **Problem**: No visibility into what steps the agent took
- **Solution**: Expandable rows in job queue showing step-by-step details
- **File**: `job_applier/api.py` (JavaScript + CSS)
- **API**: New `/queue/{job_id}/steps` endpoint
     
### 9. Human-in-the-Loop & Stop (NEW - 2026-02-04)
- **Problem**: Agent gets stuck in loops or cannot be stopped easily
- **Solution**: Pause/Resume/Stop controls. Hard cancellation for Stop
- **File**: `job_applier/runner.py`, `job_applier/agent.py`
- **API**: `/run/pause`, `/run/resume`, `/run/stop`, `/run/{id}`

### 10. Smart Retry Context (NEW - 2026-02-04)
- **Problem**: Retrying a job started from scratch without knowing *why* it failed
- **Solution**: Inject previous failure summary as "Step 0" when retrying
- **File**: `job_applier/agent.py`

---

## Known Issues / Planned Enhancements

### High Priority
1. **Heuristic form filler** - Parse DOM, match labels to profile, fill without LLM
2. **Batch operations** - Fill multiple fields in one step instead of one-by-one

### Medium Priority
3. ~~**Navigate first, think later**~~ ✅ Implemented via `initial_actions`
4. ~~**Evidence/screenshot in dashboard**~~ ✅ Expandable details show steps
5. **Better error recovery** - Retry logic for stale element errors

### Nice to Have
6. **Parallel job processing** - Run multiple browsers simultaneously
7. **Resume from failed state** - Checkpoint and resume partially-filled forms
8. **Job deduplication** - Detect if already applied to same job

---

## Architecture

```
Jobot/
├── job_applier/
│   ├── agent.py           # Core: JobApplyAgent uses browser-use Agent
│   ├── element_handlers.py # Wrapper for browser-use built-in actions
│   ├── database.py        # SQLAlchemy models (Job, ApplicationStep, Screenshot)
│   ├── db_queue.py        # JobQueueDB: SQLite-backed job storage
│   ├── step_tracker.py    # Parse browser-use history into human-readable steps
│   ├── queue.py           # [DEPRECATED] Original JSON-based storage
│   ├── runner.py          # JobRunner: Orchestrates agent execution
│   ├── migrate.py         # Migration from JSON to SQLite
│   └── api.py             # FastAPI server + HTML dashboard
├── run_applier.py         # CLI: serve, run, add, apply, migrate commands
├── job_applier.db         # SQLite database (created automatically)
├── instructions.md        # LLM prompt template (with placeholders)
└── profile.json           # User data (not committed)
```

### Database Schema

The system uses SQLite with the following tables:
- **jobs** - Core queue with seq_id, status, timestamps, intervention_reason
- **application_steps** - Tracks each step of the application process
- **element_retries** - Tracks elements that needed multiple attempts
- **screenshots** - Stores screenshot metadata (error, success, final)

### Key Classes
- `JobApplyAgent` - Wraps browser-use Agent, builds prompts, interprets results
- `JobQueueDB` - SQLite-backed queue with step tracking and screenshots
- `JobRunner` - Claims jobs from queue, runs agent, updates status
- FastAPI app - `/queue` GET/POST, `/run` POST, `/` serves dashboard

### Migration from JSON

If upgrading from an older version:
```bash
python run_applier.py migrate --check   # Check migration status
python run_applier.py migrate           # Run migration
```

---

## User Feedback from Testing

> "When the browser opens, there are many LLM calls before the first page loads. You should navigate to URL first, then inspect DOM and fill forms."
**Status**: ✅ FIXED - Using `initial_actions` for programmatic navigation

> "For each form field, there's a screenshot and LLM call. Inefficient - should parse all DOM fields, match to profile heuristically, call LLM only for ambiguous fields."
**Status**: Planned - Heuristic form filler

> "Dropdown typed 'US' but dropdown showed 'United States (+1)' - got stuck in infinite loop."
**Status**: ✅ IMPROVED - Using browser-use's built-in `select_dropdown` action

---

## Files to Review

| File | Purpose | Key Lines |
|------|---------|-----------|
| `job_applier/database.py` | SQLAlchemy models | Job, ApplicationStep, Screenshot classes |
| `job_applier/db_queue.py` | Queue operations | JobQueueDB class |
| `job_applier/agent.py` | Core agent logic | Agent creation with initial_actions |
| `job_applier/element_handlers.py` | Wrapper for browser-use actions | Simple factory function |
| `job_applier/step_tracker.py` | Parse history to steps | Action summaries for UI |
| `job_applier/api.py` | Dashboard + API | Expandable rows, step display |
| `instructions.md` | LLM prompt | Entire file (keep SHORT) |
| `.env` | Configuration | DB_PATH, MAX_STEPS, MAX_HISTORY |

---

## How to Run

```bash
cd C:\GitClone\Jobot
python run_applier.py serve
# Open http://127.0.0.1:8000
```

## How to Test a Job

1. Add URL to dashboard (or use CLI: `python run_applier.py apply "<url>"`)
2. Click "Run Next" (or job runs immediately with `apply` command)
3. Watch browser automation
4. Check `artifacts/<job-id>/result.json` for details
5. Expand job row in dashboard to see step-by-step breakdown

---

## Next Steps

Start a new session with:
> "I'm working on Jobot. Read CONTEXT.md for background. I want to implement [specific enhancement]."

---

## Reliability Fixes (2026-02-19)

### Changelog
- Instructions now require mandatory page assessment before actioning.
- Login flow now defaults to Create Account instead of Sign In.
- Added explicit login-failure stop rules and external SSO stop guidance.
- Stagnation detection now normalizes element indices in fingerprints (`#1234` -> `#N`).
- Stagnation thresholds tightened (warning at 2 repeats, hard stop at 3 repeats).
- Added URL-unchanged stagnation detection when repeated tool errors occur on the same page.
- `workday_create_account` now detects Sign In vs Create Account and handles external SSO redirect detection.
- Added `llm_thinking` column in `application_steps` for debug reasoning storage.

## Debugging Failed Applications

### Quick Check
1. `artifacts/job-NNNNN/result.json` for final status and stagnation reason.
2. `artifacts/job-NNNNN/recording.gif` for visual replay.

### Deep Analysis
1. `artifacts/job-NNNNN/trace.jsonl` for per-step model output and loop signals.
2. Query database:
   - `SELECT step_number, action_type, element_description, error_message, llm_thinking FROM application_steps WHERE job_id='...' ORDER BY step_number;`
3. Look for repeated actions, ignored login errors, and same-URL loops.

### Common Failure Patterns
- Login loops: Sign In attempted without account creation path.
- Stagnation: repeated action on same effective element or same URL with repeated errors.
- External SSO redirect: domain changed from job site to corporate auth provider.
- Consent checkbox block: requires "Read More" / scroll before toggle.

## Known Issues Update
- Resolved: login loops caused by dynamic element indices bypassing stagnation checks.
- Resolved: Workday Sign In pages being treated like Create Account pages.
- Resolved: inability to inspect captured model reasoning separately from UI memory.
- Remaining: heuristic non-LLM form filling and broader stale-element recovery.

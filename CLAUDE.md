# CLAUDE.md

Repo guide for the AI Revenue Recovery Agent (Razorpay Buildathon, Track 03).
See `revenue-recovery-agent-prd.md` for the full product spec and
`revenue-recovery-agent-prd.md` §14 for the original 12-day plan (this repo
follows the phased breakdown in the approved plan instead — see phase status
table below).

## Key deviations from the PRD

- **LLM**: Gemini API (`google-genai`), not Claude/Anthropic — cost constraint.
- **DB**: Postgres via local Docker Compose, not cloud Supabase.
- **Voice TTS (Sarvam)**: deferred, out of scope for now — text-transcript
  voice simulation only.

## Repo layout

```
/backend
  /app
    /simulation      # environment generator, hidden recoverability model
    /detection        # root cause classifiers (rules + Gemini)
    /policy            # action proposal (Gemini) + guardrail enforcement
    /execution         # channel connectors (mock), voice conversation runner
    /audit             # event logging, batch rollup queries
    /api                # FastAPI routes
    /db                 # SQLAlchemy session/Base
    models.py           # SQLAlchemy models (Case, Customer, Attempt, AuditEvent)
  /alembic             # migrations
  /tests
  docker-compose.yml    # local Postgres
  .env.example
/frontend                # Next.js (App Router, TypeScript, Tailwind)
/revenue-recovery-agent-prd.md
```

## Running locally

### Backend + DB

```
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY
docker compose up -d
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.api.main:app --reload
curl http://localhost:8000/health
```

### Seed a synthetic batch and inspect it

```
cd backend
.venv/Scripts/python.exe -m app.simulation.seed --n 200 --seed 42
.venv/Scripts/python.exe scripts/inspect_batch.py
```

`app/simulation/generator.py` produces Customer + Case rows (root_cause
left null — filled by detection in Phase 2). `app/simulation/recoverability.py`
holds the **hidden** recoverability model: detection/policy code must never
import it, only the Phase 4 execution layer rolls against it to produce
outcomes.

### Run detection over a seeded batch

```
cd backend
.venv/Scripts/python.exe scripts/run_detection.py
```

Rules-first (`app/detection/rules.py`) for unambiguous decline codes,
Gemini fallback (`app/detection/llm_classifier.py`) for free-text/ambiguous
messages — only ~5% of payment/mandate cases hit the LLM path by design
(kept low deliberately, mind Gemini free-tier rate limits when re-seeding
large batches and re-running detection repeatedly). Receivables are
skipped — their root-cause taxonomy is built in Phase 6.

**Note on model name**: `gemini-2.0-flash` (the PRD-era default) 404s as
of this build — the API redirects to `gemini-3.6-flash`, which is now the
default in `app/config.py`. If Gemini deprecates models again, update
`GEMINI_MODEL` in `.env`/`app/config.py`.

### Run the policy engine guardrail demo

```
cd backend
.venv/Scripts/python.exe scripts/run_policy_demo.py
```

Four hand-built scenarios proving the guardrail layer (`app/policy/guardrails.py`)
actually overrides the LLM, not just exists: fraud auto-escalate, a
DND-blocks-voice_call substitution (forced deterministically, not left to
chance — see the script's `_FixedResponseClient`), a max-contacts
auto-escalate, and one normal real-Gemini proposal that passes compliance
cleanly. `app/policy/engine.py:decide_action` is the entry point the
Phase 4 execution layer will call per case.

Stopping rules (`check_stopping_rules`) are absolute and skip the LLM
call entirely when they fire. Compliance rules (`check_compliance`) are
substitutive — they swap in `send_reminder` as the universal compliant
fallback rather than blocking the case outright.

### Run a full batch end-to-end (detection -> policy -> execution)

```
cd backend
.venv/Scripts/python.exe -m app.simulation.seed --n 20 --seed 200
.venv/Scripts/python.exe scripts/run_batch.py
```

`app/execution/runner.py:run_batch` loops every open payment_failure/
mandate_failure case through `decide_action` + a mock connector
(`app/execution/connectors.py`) until it reaches a terminal status
(`recovered`/`written_off`/`escalated_human`). Each case gets its own
simulated clock (jumps ~25h per round) so multi-week recovery journeys
play out in one script run. Receivables are excluded from the runner
until Phase 6 gives them a root-cause taxonomy.

**Gemini free-tier quota**: `gemini-3.6-flash`'s free tier caps out at
20 requests/day — a single batch run blows through that immediately.
Switched the default model to `gemini-3.5-flash-lite`, which has a much
higher free-tier daily quota and works fine for our structured-JSON
calls. Both `classify_by_llm` and `propose_action` now catch
`google.genai.errors.APIError` and fail safe (same fallback as
unparseable output) rather than crashing the batch — so a rate limit or
network blip degrades gracefully instead of taking down a whole run. If
you see an unusually high `escalated_human` count in a batch summary,
check whether the quota was hit (fail-safe fallback is `escalate_human`)
before assuming the policy engine is behaving badly.

Note: the dev Postgres DB accumulates cases across every seed run in
this project's history (see the Phase 1 note above on `test_seed.py`) —
`run_batch`'s summary numbers are cumulative across everything ever
seeded, not just your most recent batch. Reset with `docker compose down
-v && docker compose up -d && alembic upgrade head` for a clean slate.

### Run one live voice recovery call

```
cd backend
.venv/Scripts/python.exe scripts/run_voice_demo.py cooperative
.venv/Scripts/python.exe scripts/run_voice_demo.py hostile
```

`app/execution/voice.py` runs a capped 6-turn Hinglish conversation
between a Gemini-played recovery agent and a Gemini-played synthetic
customer whose behavior follows the profile argument (cooperative /
evasive / unresponsive / hostile), then a separate extraction call
parses the transcript into `{consent, action, promise_to_pay_date}`.
This is 7 real Gemini calls per run — mind the quota.

Wired into the batch runner via `execute_voice_call` in
`app/execution/connectors.py`: the conversation shapes how an outcome is
*labeled* (e.g. `promise_to_pay` vs generic `success`), but the same
hidden recoverability model still decides whether money actually moves
— consistent with every other channel, not a separate "the LLM decides
the outcome" path.

### Run the receivables-only demo

```
cd backend
.venv/Scripts/python.exe scripts/run_receivables_demo.py
```

Three hand-built receivable scenarios (disputed, overdue_late,
overdue_mid), scoped via `run_batch`'s `case_ids` filter so it doesn't
sweep every accumulated case in the dev DB. `app/detection/receivables.py`
classifies deterministically from `due_at`/`disputed` — no LLM needed,
unlike payment/mandate root causes. Everything downstream (allowed
action subset, guardrails, connectors) was already generic across case
types from Phases 3-5; this phase was mostly proving that, plus fixing
two real bugs it surfaced:

- **`created_at` was conflated with `due_at`** for receivables (Phase 1
  generator bug) — a 60-day-overdue invoice looked 60 days old the moment
  it was created, immediately tripping the 14-day case-age escalation
  guardrail before any real attempt happened. Fixed: `created_at` now
  reflects when the recovery case was opened, independent of `due_at`.
- **`AuditEvent.timestamp` collisions** — `datetime.utcnow()` as a
  Python-side default produced identical timestamps for events written
  in the same flush (e.g. `action_proposed` immediately followed by
  `compliance_check`), breaking chronological ordering. Fixed: switched
  to Postgres server-side `clock_timestamp()`, evaluated per row.

### API routes (dashboard backend)

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.api.main:app --reload
```

- `POST /batches/run` `{"n_cases": 200, "seed": null}` — generates + persists
  a fresh batch tagged with a new `batch_id`, runs it through the full
  pipeline, returns `{batch_id, n_customers, n_cases, summary}`.
- `GET /batches/{batch_id}/summary` — the PRD §11 dashboard rollup: ₹ at
  risk/recovered, recovery rate overall + by root cause, status counts,
  `stopping_rule_triggers`, `compliance_substitutions`.
- `GET /cases?batch_id=&status=&type=` — filtered case list.
- `GET /cases/{case_id}` — full chronological timeline (all AuditEvents +
  Attempts) for one case.

`app/audit/rollup.py` and `app/audit/timeline.py` hold the underlying
queries, both scoped by `batch_id` so they never sweep the whole
cumulative dev DB — a nice side effect of adding `batch_id` in this
phase. Every case seeded before this phase has `batch_id = NULL` and
simply won't appear in any batch-scoped query.

Example walkthrough:
```
curl -s -X POST http://localhost:8000/batches/run -H "Content-Type: application/json" -d '{"n_cases": 10, "seed": 500}'
curl -s "http://localhost:8000/batches/<batch_id>/summary"
curl -s "http://localhost:8000/cases?batch_id=<batch_id>&status=recovered"
curl -s "http://localhost:8000/cases/<case_id>"
```

**Note on burst rate limits**: a live 10-case batch run surfaced that
Gemini's free tier also enforces a requests-per-minute cap, not just the
daily one - a burst of policy calls across many cases in a short window
can trip it mid-batch. The existing fail-safe (catches `APIError`, falls
back to `escalate_human`) handled it gracefully with zero crash, and the
new `/cases/{id}` drill-down is exactly how you'd notice/diagnose it in
practice (look for `"LLM proposal was unparseable or invalid; failing
safe to human escalation."` in an `action_proposed` payload). Not fixed
here - noted as a real risk for Phase 9 polish if larger batches are
needed for the final demo (PRD §16 already flagged this as an open risk).

### Tests

```
cd backend
.venv/Scripts/python.exe -m pytest -q
```

LLM-dependent tests are mocked by default. Real-Gemini smoke tests are gated
behind `ENABLE_LIVE_LLM_TESTS=true` in `.env` so a normal test run never
silently burns API cost.

Note: `test_seed.py` writes real rows into the local dev Postgres (no
separate test DB yet) — expect row counts in `inspect_batch.py` to include
rows left over from test runs. Fine for buildathon scope; if it gets
annoying, `docker compose down -v && docker compose up -d && alembic
upgrade head` resets the DB.

### Frontend

```
cd frontend
npm install
npm run dev
```

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (default matches docker-compose.yml) |
| `GEMINI_API_KEY` | Gemini API key for detection/policy/voice LLM calls |
| `GEMINI_MODEL` | Gemini model id (default `gemini-2.0-flash`) |
| `ENABLE_LIVE_LLM_TESTS` | `true` to run real-Gemini smoke tests |

## Phase status

| Phase | Description | Status |
|---|---|---|
| 0 | Scaffolding & environment | Done |
| 1 | Data models + synthetic environment generator + seed script | Done |
| 2 | Detection layer | Done |
| 3 | Policy engine (proposal + guardrails) | Done |
| 4 | Execution layer + batch runner | Done |
| 5 | Voice recovery channel | Done |
| 6 | B2B receivables flow | Done |
| 7 | Audit trail storage + dashboard API | Done |
| 8 | Frontend (dashboard, run, case drill-down) | Not started |
| 9 | Seed-guarantee, polish, demo rehearsal | Not started |

Full phase plan: `C:\Users\Dewashish Lambore\.claude\plans\go-through-the-prd-snuggly-cerf.md`

## Conventions

- Small, frequent commits — one logical unit per commit (a module, a route, a
  migration, a test file), not one giant commit per phase.
- Guardrails (stopping rules + compliance rules, PRD §9.2–9.3) are pure
  deterministic code with their own unit tests — never prompt-only logic.
- Every phase ends with: tests passing, a manual CLI/API walkthrough the user
  runs themselves, this file updated, and a commit.

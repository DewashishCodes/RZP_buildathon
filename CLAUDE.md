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

- `POST /batches/run` `{"merchant_id": "...", "n_cases": 200, "seed": null, "instant": true}` —
  generates + persists a fresh batch tagged with a new `batch_id` and the
  given tenant, runs it through the full pipeline, returns
  `{batch_id, n_customers, n_cases, summary}`. `merchant_id` is required —
  see `GET /merchants` below. `instant=false` leaves non-terminal cases
  scheduled instead of resolving them fully (see the scheduling section
  above).
- `GET /batches/{batch_id}/summary` — the PRD §11 dashboard rollup: ₹ at
  risk/recovered, recovery rate overall + by root cause, status counts,
  `stopping_rule_triggers`, `compliance_substitutions`.
- `GET /cases?batch_id=&merchant_id=&status=&type=` — filtered case list.
- `GET /cases/scheduled?merchant_id=` — cases currently waiting on a
  deferred round (`next_action_at` set).
- `GET /cases/{case_id}` — full chronological timeline (all AuditEvents +
  Attempts) for one case.
- `GET /merchants` — the demo tenants.
- `GET /tickets?merchant_id=&status=`, `GET /tickets/{id}`.
- `POST /jobs/run-due?merchant_id=` — advances every scheduled case for
  that tenant (or all tenants if omitted).

`app/audit/rollup.py` and `app/audit/timeline.py` hold the underlying
queries, both scoped by `batch_id` so they never sweep the whole
cumulative dev DB — a nice side effect of adding `batch_id` in this
phase. Every case seeded before this phase has `batch_id = NULL` and
simply won't appear in any batch-scoped query.

Example walkthrough:
```
MERCHANT_ID=$(curl -s http://localhost:8000/merchants | python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST http://localhost:8000/batches/run -H "Content-Type: application/json" -d "{\"merchant_id\": \"$MERCHANT_ID\", \"n_cases\": 10, \"seed\": 500}"
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
Observed in practice: a live 25-case run showed heavy escalation from
this; a 10-case run at the same time came out at 80%+ recovery. Keep
batch runs small (~10-15 cases) until this gets throttling/backoff.

### Frontend (dashboard, run, case drill-down)

```
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, defaults to localhost:8000
npm run dev
```

Requires the backend running (`uvicorn app.api.main:app --reload`) with
CORS enabled for `http://localhost:3000` (already configured in
`app/api/main.py`, dev-only).

- `/` — landing page.
- `/run` — trigger a new batch for the active merchant (`POST /batches/run`),
  with a "Realistic scheduling mode" toggle; shows the result inline with
  a link to the dashboard.
- `/dashboard?batch=<id>` — batch rollup: ₹ at risk/recovered, recovery
  rate, stopping-rule/compliance-substitution counters, recovery-by-root-
  cause table, Scheduled Actions panel (merchant-wide), case list.
- `/cases/[id]` — full chronological audit timeline (every AuditEvent's
  payload rendered) + attempts, with a collapsible call transcript for
  `voice_call` attempts. Server-rendered.
- `/tickets` — support tickets for the active merchant.

The nav's merchant dropdown (top right) scopes everything to one tenant.
`lib/api.ts` is the typed client for every backend route.

## Post-Phase-8 additions: multi-tenancy, support tickets, real scheduling

Added after Phase 8 in response to "how would a business actually integrate
this" — three things needed to make the demo answer that question instead
of only showing single-tenant instant-resolve batches.

### Multi-tenancy (no auth)

`Merchant` model + `Case.merchant_id`. Three demo tenants (Kirana Mart,
CloudStack SaaS, Urban Wheels) auto-seeded on backend startup
(`app/simulation/merchants.py`, idempotent by slug) via a FastAPI lifespan
hook — no manual step, no signup flow. **Deliberately no auth** — tenancy
is enforced by scoping every query to a `merchant_id`, not a login wall,
to keep judge/demo access frictionless. The frontend nav has a merchant
dropdown (`components/merchant-context.tsx`, persisted to localStorage)
that scopes `/run`, `/tickets`, and the dashboard's Scheduled Actions
panel. `POST /batches/run` now requires `merchant_id`.

### Support tickets (in-house mock, not a real external tool)

`Ticket` model, auto-created by `app/execution/tickets.py:create_ticket_for_case`
every time a case hits `escalate_human` (idempotent per case). Priority
derived from the guardrail rule: fraud/dispute → urgent, exhausted-channels
→ high, everything else → normal. `GET /tickets`, `GET /tickets/{id}`,
frontend `/tickets` page. This is a from-scratch mock, not an integration
with Freshdesk/Zendesk/etc. — the point was to give `escalate_human`
somewhere real to land for the demo, not to build a real support-tool
integration.

### Real scheduling (not just simulated time-jumps)

`run_batch(..., instant=True)` (default) is unchanged — each case's
`sim_now` clock still jumps forward per round so the dashboard populates
immediately. `instant=False` runs **exactly one round per case**, then —
if not terminal — persists `Case.next_action_at` (a real timestamp) and
stops; the case sits with `status="recovering"` until something advances
it. `process_due_cases()` (`POST /jobs/run-due`) advances every case
currently scheduled, mirroring what a real cron/job queue would do —
invoked manually here (not a background scheduler) so a live demo doesn't
have to wait for real wall-clock time to pass. Frontend: `/run`'s
"Realistic scheduling mode" checkbox, and the dashboard's
**Scheduled Actions** panel (`components/scheduled-actions.tsx`) with a
"Process due jobs now" button.

**Bug found and fixed while building this**: a case left `recovering` by
a non-instant round isn't a terminal status, so it can get swept up again
by a *later, unrelated* instant-mode `run_batch` call (any call without a
`case_ids` filter processes every non-terminal case in scope, regardless
of which mode created it). The terminal branches only cleared
`next_action_at` in the deferred-mode wrapper, not centrally, so a case
could reach `escalated_human`/`recovered`/`written_off` while still
carrying a stale future `next_action_at` — `GET /cases/scheduled` would
then list already-finished cases as if still pending. Fixed by clearing
`next_action_at` in `_run_case_round`'s three terminal branches directly.
Caught by curling the real walkthrough, not by the test suite (existing
tests didn't exercise "non-instant round, then later an unrelated instant
run" on the same case) — a regression test now covers this exact sequence.

### Frontend design system

Dark-only theme built on the `dataviz` skill's validated reference
palette (not arbitrary Tailwind neutrals) — status colors and the chart
accent hue are contrast/CVD-checked against this app's exact dark
surface. Inspiration: Linear's chrome/typography, Ramp's product
surfaces (tables, badges, filter chips), Mercury's stat tiles/CTAs,
Sentry's event-timeline pattern for the case drill-down.

- `app/globals.css` — design tokens as Tailwind v4 `@theme` vars
  (`bg-surface-1`, `text-status-good`, etc.)
- `components/status-badge.tsx` — icon + label + status color, per the
  dataviz rule that a status color never carries meaning alone
- `components/stat-tile.tsx` — hero-number cards for the dashboard KPI row
- `components/progress-row.tsx` — the "meter" pattern for recovery-by-
  root-cause (one accent hue = recovered share; row label already
  carries identity via text, so this isn't a categorical-color problem)
- `components/event-timeline.tsx` — the Sentry-style vertical timeline
  for `/cases/[id]`
- `components/nav.tsx`, `components/icons.tsx` — nav chrome, small
  hand-built icon set (no icon library dependency)

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
| `GEMINI_MODEL` | Gemini model id (default `gemini-3.5-flash-lite` — see the rate-limit notes above) |
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
| 8 | Frontend (dashboard, run, case drill-down) | Done |
| 9 | Seed-guarantee, polish, demo rehearsal | Not started |

Full phase plan: `C:\Users\Dewashish Lambore\.claude\plans\go-through-the-prd-snuggly-cerf.md`

## Conventions

- Small, frequent commits — one logical unit per commit (a module, a route, a
  migration, a test file), not one giant commit per phase.
- Guardrails (stopping rules + compliance rules, PRD §9.2–9.3) are pure
  deterministic code with their own unit tests — never prompt-only logic.
- Every phase ends with: tests passing, a manual CLI/API walkthrough the user
  runs themselves, this file updated, and a commit.

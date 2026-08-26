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
safe to human escalation."` in an `action_proposed` payload).
Observed in practice: a live 25-case run showed heavy escalation from
this; a 10-case run at the same time came out at 80%+ recovery.

**Fixed since**: `app/llm_resilience.py` now wraps every Gemini call with
a client-side token-bucket rate limiter (`LLM_REQUESTS_PER_MINUTE`,
default 15), retry with exponential backoff on transient errors (429/5xx/
timeouts, honoring the server's `Retry-After` header), and a classification
cache keyed on the raw failure message (`app/detection/llm_classifier.py`
- identical messages recur constantly in synthetic data, so this removes
most classifier calls per batch). Only exhausted retries still reach the
fail-safe fallbacks; keep batches modest anyway since free-tier *daily*
quotas can't be paced around.

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

## Phase 9: seed-guarantee, demo script, known limitations

### Seed-guarantee (PRD §16: "don't rely on random generation alone")

`app/simulation/guaranteed_cases.py` adds six hand-crafted scenario cases
on top of every random batch — both `app/simulation/seed.py:seed_batch`
(default `include_guaranteed=True`) and `POST /batches/run` include them
unconditionally, so even a demo-sized batch of 5-10 random cases is
certain to contain each key scenario. Four are **fully deterministic
guarantees** (pure `check_stopping_rules` code, no LLM involved, so they
cannot fail to fire):

- `fraud_suspected` payment case → `fraud_or_dispute_auto_escalate`
- `disputed` receivable → `fraud_or_dispute_auto_escalate`
- a payment case pre-loaded with 4 prior `Attempt` rows → `max_total_contacts`
- a payment case backdated 16 days → `case_age_exceeded`

The other two are **biased, not guaranteed** — they depend on what the
real Gemini policy call actually proposes, and there's no way to force
that without substituting a fixed LLM response (which would defeat the
point of a live batch):

- a DND-registered customer on a severely overdue, high-value,
  already-SMS-nudged receivable — the shape of case a policy should
  escalate to `voice_call`, which the DND compliance rule then has to
  substitute back to `send_reminder`. Verified live (see walkthrough
  below): Gemini proposed `voice_call` three rounds running, DND
  substituted it every time, then `max_total_contacts` escalated it —
  exactly the PRD §15 step 6 demo moment.
- a cooperative customer on a mid-overdue receivable — the shape most
  likely to produce a `promise_to_pay` outcome (honored or broken),
  since `request_promise_to_pay` already has a 50% "gives a promise"
  base rate for `overdue_mid` in the hidden recoverability model.

`tests/test_guaranteed_cases.py` asserts the four deterministic
scenarios actually classify and trip their stopping rule; the DND/PTP
scenarios are only asserted on their input shape (can't unit-test real
LLM behavior).

### Demo script rehearsal (PRD §15)

Ran the full script live against a fresh batch: trigger a batch →
dashboard populates → drill into an `insufficient_funds` case → drill
into a `card_expired`/`send_update_link` case → drill into the
`max_total_contacts`-escalated case (guardrail firing) → drill into the
DND-substitution case (compliance logic firing) → play a voice
transcript → read one case's audit trail end-to-end. All eight steps
work as scripted against the guaranteed-cases batch.

**Known limitation carried into the demo**: a burst of several real
Gemini policy calls within one small batch can trip the free-tier
per-minute rate limit mid-run (see the burst-rate-limit note earlier in
this file); the fail-safe (`escalate_human` with rationale "LLM proposal
was unparseable or invalid; failing safe to human escalation") handles
it gracefully but can occasionally consume the promise-to-pay bias
case's LLM call before it gets a real proposal. Not a correctness bug —
re-running the batch (a fresh Gemini call budget) reliably reproduces the
promise-to-pay scenario. Keep batch runs small (~10-15 cases total,
which the 6 guaranteed cases already count toward) per the existing
rate-limit guidance.

## Demo reliability (Track A)

### Quota strategy: pre-run + history as backup

Gemini's free tier is the single biggest live-demo risk (daily cap,
per-minute burst cap, both documented above) - the mitigation is
procedural, not more code:

1. **Pre-run a batch before the actual demo slot**, ~10-15 cases
   (guaranteed-cases scenarios included), and confirm it reached the
   full drill-down set (recovered `insufficient_funds` case, a
   `card_expired`/`send_update_link` case, a `max_total_contacts`
   escalation, a DND compliance substitution) via one-click demo mode's
   auto-derived story list (`/run?demo=1`).
2. **During the live demo, don't re-run Gemini calls you don't need.**
   Walk the pre-run batch's dashboard and case drill-downs first - the
   audit trail already has everything (rationale, guardrail fires,
   substitutions) without spending fresh quota.
3. **`/history` is the fallback if live Gemini calls degrade mid-demo**
   (a burst trips the per-minute cap, or the daily cap is close). Every
   past run stays browsable there indefinitely - if a fresh batch
   triggered live comes back heavy on `escalated_human` (the fail-safe
   fallback for an exhausted-retry Gemini call, not a policy-engine
   bug - see the burst-rate-limit note above), pivot to a pre-run batch
   from history rather than troubleshooting quota live.
4. If quota is tight on the day, favor `instant=true` (default) batches
   over `instant=false` scheduling-mode demos - non-instant mode still
   makes the same number of Gemini calls, just spread across more
   `POST /jobs/run-due` invocations, which is more surface area for a
   burst to land on mid-demo.

### Frontend polish

Every page/route has its own browser-tab title (`app/*/layout.tsx` for
the client-rendered pages under `/dashboard`, `/history`, `/run`,
`/tickets`; `generateMetadata` on `/cases/[id]` since it's server-
rendered and can title itself by root cause) - previously every route
showed the same root title, indistinguishable in a tab bar or browser
history during a live walkthrough. Icon-only interactive elements
(the scheduled-actions "view case" arrow, the call-transcript
disclosure toggle) got `aria-label`/`aria-expanded`; decorative icons
already paired with a visible text label got `aria-hidden`. Empty
states were already solid across the app (no-batch-selected, no
tickets yet, no batch history, nothing scheduled) - audited, not
rebuilt.

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (default matches docker-compose.yml) |
| `GEMINI_API_KEY` | Gemini API key for detection/policy/voice LLM calls |
| `GEMINI_MODEL` | Gemini model id (default `gemini-3.5-flash-lite` — see the rate-limit notes above) |
| `ENABLE_LIVE_LLM_TESTS` | `true` to run real-Gemini smoke tests |
| `LLM_REQUESTS_PER_MINUTE` | Client-side token-bucket cap for Gemini calls (`app/llm_resilience.py`, default 15; 0 disables pacing) |
| `LLM_MAX_ATTEMPTS` | Retry attempts for transient LLM errors (default 3) |
| `LLM_BACKOFF_BASE_SECONDS` | Exponential-backoff base in seconds (default 2.0) |
| `RAZORPAY_WEBHOOK_SECRET` | HMAC-SHA256 secret for `POST /webhooks/razorpay`'s signature (empty skips verification) |
| `REQUIRE_MERCHANT_API_KEY` | `true` to require `X-API-Key` on `POST /batches/run` and scoped `POST /jobs/run-due` (default `false`) |

### Correctness hardening (Aug 25)

A review pass fixed five latent issues; tests cover each:

- **Sim-clock leak** — `_normalize_retry_params` built retry dates from
  wall clock while the runner advances a simulated clock days ahead, so
  LLM-chosen retry offsets were silently discarded. The runner's clock now
  threads through `decide_action` into `propose_action`.
- **Uncommitted audit events** — the runner's `no_action` branch returned
  without committing, leaving that round's AuditEvents pending until an
  arbitrary later commit (lost on crash). It commits like every other branch.
- **Naive datetime defaults** — `Case.created_at`/`Attempt.timestamp` used
  deprecated Python-side `datetime.utcnow`; both are server-side `now()`
  now (migration `a1f2c3d4e5b6`, which also adds the missing indexes:
  `attempts.case_id`, `audit_events.case_id/event_type`,
  `cases.status/created_at`).
- **Cumulative summary footgun** — `run_batch`'s returned summary aggregated
  the whole cases table (cumulative across every seed run ever), while the
  API route recomputed batch-scoped numbers. It's scoped to exactly the
  cases the run processed now, so CLI scripts and the API agree.
- **Unbounded inputs** — `n_cases` capped at 500 server-side (422 beyond),
  `GET /cases`/`GET /tickets` limit capped and offset-paginated, and
  status/type filters validated against the taxonomy (400 on typos instead
  of silently-empty results).

Also: the runner eager-loads customer+attempts per batch fetch (was an N+1),
and `tests/conftest.py` disables rate-limit/backoff sleeps via env vars so
the suite stays fast.

## Phase 10: background batches, live progress, demo-surface upgrades

### Background batch runs (POST /batches/run `background: true`)

The pipeline used to run synchronously inside the HTTP request — an n=200
batch held the connection open for minutes of paced Gemini calls, and the
/run page showed a static "Running…" with no feedback. Now:

- `POST /batches/run` accepts `"background": true` (default false — the
  sync contract and all existing tests are unchanged): it seeds the batch,
  returns `{batch_id}` immediately (observed ~200ms), and runs the pipeline
  as a FastAPI BackgroundTask.
- A new `BatchRun` model + table (`migration b7e8d2a4c9f1`) tracks the
  lifecycle: queued → running → complete|failed, with the final rollup
  stored in `BatchRun.summary` on completion and any exception captured as
  `error` instead of vanishing into a detached thread. Legacy sync batches
  have no row; their progress derives purely from case statuses.
- `GET /batches/{id}/progress` reports live counts straight off the cases
  table (`total/resolved/recovered_cases`, `recovered_amount`,
  `at_risk_amount`) so numbers tick up while the agent works.
- Frontend `/run` posts in background mode and polls progress every 1.5s,
  showing a live progress bar + ticking ₹ recovered; the dashboard polls
  every 4s while any case is still open/recovering, then stops.

### Demo-surface additions

- **`GET /batches/{id}/guardrails`** (`app/audit/rollup.py:guardrail_interventions`)
  — every stopping-rule fire + compliance substitution in the batch,
  newest first, with rule name and reason. The dashboard renders this as
  the "Guardrails in action" feed (`components/guardrail-feed.tsx`),
  turning the two proof counters into clickable stories.
- **`GET /batches/{id}/curve`** (`recovery_curve`) — cumulative ₹
  recovered at each recovery moment. Rendered as a hand-drawn inline-SVG
  rising line (`components/recovery-chart.tsx`, zero chart deps).
- **"Why this action?" card** on `/cases/[id]` — surfaces the first
  `action_proposed` rationale plus its compliance verdict above the fold;
  answers the first question judges ask without scrolling the timeline.
- **Chat-bubble transcripts + browser TTS** (`components/call-transcript.tsx`)
  — voice transcripts render as agent/customer chat bubbles with a
  "Play agent audio" button using the Web Speech API (prefers a hi-IN
  voice). This delivers PRD §10's deferred Sarvam-TTS stretch goal at zero
  cost; the extraction pipeline is untouched.
- **Interleaved timeline** — AuditEvents and Attempts now merge into one
  chronological thread in `/cases/[id]` (they were two disconnected
  sections), each attempt carrying its transcript inline.
- **One-click demo mode** — the landing page's "Run demo batch" button goes
  to `/run?demo=1` (prefills n=10, seed=42); when the batch finishes, the
  page auto-derives the PRD §15 drill-downs (recovered insufficient_funds
  case, card_expired link case, DND substitution from the guardrails feed,
  escalated cases) into a click-to-story list, so the live walkthrough is
  one click per beat instead of hunting through tables.

### Test suite notes

`tests/test_llm_resilience.py` covers retry/backoff/rate-limit/Retry-After
classification; `tests/test_api_batches.py` covers the background flow
including the failure path (pipeline exception → `phase="failed"` +
error on the row, HTTP still 200); `tests/test_dashboard_extras.py`
covers the feed and curve queries including cross-batch isolation.
Note for future work: DB-backed tests still write to the dev Postgres —
the conftest only disables LLM pacing; transaction-per-test isolation is
the known next step.

**Resolved**: see the Pre-public hardening section below —
`tests/conftest.py`'s `db_transaction` fixture now wraps every test in a
transaction rolled back at teardown.

## Pre-public hardening (Track C)

A pass done before making the repo public, in preparation for the
buildathon submission. Ordered C → B → A → D against the submission
form's asks; this is Track C (engineering hygiene) — see Track B/A/D
notes below once those land.

- **Secrets audit** — `backend/.env` (holds the real `GEMINI_API_KEY`)
  was already covered by `.gitignore` and never committed; checked the
  full history with `git log --all -p -S "AIza"` and a tracked-file grep
  for API-key-shaped strings — clean, nothing to remediate.
- **Dockerfiles + one-command full-stack compose** — `backend/Dockerfile`
  (runs `alembic upgrade head` then `uvicorn`) and `frontend/Dockerfile`
  (multi-stage, Next.js `output: "standalone"`). Root `docker-compose.yml`
  wires db + backend + frontend so `docker compose up` (with
  `GEMINI_API_KEY` in the environment) boots the whole stack for a judge
  without a local Python/Node install; `backend/docker-compose.yml`
  (db-only) is unchanged for the existing local dev workflow above.
- **Test-DB isolation** — `tests/conftest.py`'s `db_transaction` autouse
  fixture wraps every test in one transaction + SAVEPOINT, rolled back at
  teardown (the standard SQLAlchemy "join a session into an external
  transaction" recipe). `app.db.session.SessionLocal` became a plain
  function reading a swappable module-level factory at call time, so the
  override reaches every `SessionLocal()` call site without patching each
  one individually. This immediately caught `test_api_merchants_tickets_jobs.py`
  silently depending on merchant rows another test file happened to
  commit first — fixed by seeding explicitly per test. Also reset the dev
  Postgres volume to clear years of pre-fixture accumulation; the suite
  now runs in ~13s (was ~43s) and leaves zero rows behind.
- **Architecture-invariant test** — already landed prior to this pass
  (`tests/test_architecture_invariants.py`): asserts detection/policy
  modules never import the hidden recoverability model.
- **Atomic due-case claiming** — `process_due_cases` (`POST
  /jobs/run-due`) now claims rows with `SELECT ... FOR UPDATE SKIP
  LOCKED` instead of a plain `SELECT`, so two overlapping calls (a real
  cron firing twice, a judge double-clicking "process due jobs now")
  can't both grab and re-run the same case.
- **Idempotency key on batch runs** — `POST /batches/run` accepts an
  optional `idempotency_key`; a retry with the same `(merchant_id,
  idempotency_key)` returns the original batch instead of seeding a
  duplicate one. `BatchRun` rows are now always created (previously only
  for `background=true`) so idempotency has somewhere to look the key up
  regardless of mode, and the sync path now flips its own row through
  `running → complete` like the background path already did. A race on
  the same key hits the table's partial unique index
  (migration `c4f9a1e2b3d5`); the loser's `IntegrityError` is caught and
  it returns the winner's batch instead of erroring.
- **Fail-fast Gemini key** — `get_client()` now raises immediately with
  an actionable message if `GEMINI_API_KEY` is unset, instead of an
  opaque auth error on the first real call.
- **DB-pinging `/health`** — no longer a static `{"status": "ok"}`; it
  runs `SELECT 1` against Postgres and reports whether
  `GEMINI_API_KEY` is configured, so a misconfigured environment
  surfaces at the health check instead of mid-batch during a demo.

## Real-world credibility (Track B)

Done after Track C, in prep for the buildathon submission's "how does
this touch the real world" questions.

- **`POST /webhooks/razorpay`** (`app/api/webhooks.py`) — mock ingestion
  that mirrors Razorpay's actual webhook scheme: `X-Razorpay-Signature`
  is the HMAC-SHA256 hex digest of the raw body, keyed by
  `RAZORPAY_WEBHOOK_SECRET` (empty by default, so the demo endpoint works
  without provisioning a secret). `payment.captured` resolves the
  referenced case (looked up via `payload.payment.entity.notes.case_id`);
  `payment.failed` records a webhook `Attempt` without resolving it, same
  as any other channel's failed attempt. This is independent of the
  batch runner's simulated recoverability-model dice roll — the "how
  does this touch real Razorpay" answer for the submission.
- **Provider adapter interface** (`app/execution/providers.py`) —
  `ChannelProvider` is the seam where a real SMS/voice/email/WhatsApp API
  call would actually happen, separate from *whether* an attempt
  succeeds (still decided by the hidden recoverability model).
  `LoggingChannelProvider` is the only implementation: logs a structured
  "sent" record and returns a synthetic receipt id. `run_batch`/
  `process_due_cases` take an optional `provider` (same injection
  pattern as `llm_client`); the runner records the receipt on the
  `action_executed` AuditEvent.
- **Opt-in per-merchant API-key auth** (`app/api/auth.py`) —
  `REQUIRE_MERCHANT_API_KEY` defaults to false (this project's existing
  no-auth-wall stance for frictionless judge/demo access). When on,
  `POST /batches/run` and merchant-scoped `POST /jobs/run-due` check
  `X-API-Key` against `Merchant.api_key`, generated for every seeded
  merchant regardless of the setting. Never returned by `GET /merchants`
  (an open endpoint) — `scripts/show_merchant_api_keys.py` prints it for
  local testing.
- **Structured JSON logging + request IDs** (`app/logging_config.py`) —
  every app-level log line is one JSON object (timestamp, level, logger,
  message, plus any `extra={...}` fields); a `request_id_middleware`
  mints or reuses an inbound `X-Request-ID`, stores it on a contextvar
  the formatter reads, and echoes it on the response header. Covers this
  app's own business-event logging (batch runs, webhook events, provider
  dispatches) — uvicorn's own access-log lines keep their default format
  since uvicorn wires its own loggers separately from the root logger.

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
| 9 | Seed-guarantee, polish, demo rehearsal | Done |

Full phase plan: `C:\Users\Dewashish Lambore\.claude\plans\go-through-the-prd-snuggly-cerf.md`

## Conventions

- Small, frequent commits — one logical unit per commit (a module, a route, a
  migration, a test file), not one giant commit per phase.
- Guardrails (stopping rules + compliance rules, PRD §9.2–9.3) are pure
  deterministic code with their own unit tests — never prompt-only logic.
- Every phase ends with: tests passing, a manual CLI/API walkthrough the user
  runs themselves, this file updated, and a commit.

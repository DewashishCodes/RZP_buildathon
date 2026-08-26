# Improvement Report: Frontend, Backend, Scale, Real World

*Written Aug 25, 2026 · ~9 days before the Sept 3 submission deadline.*

Based on a full read of `backend/app/`, `backend/tests/`, `backend/scripts/`, migrations, infra,
and every frontend page/component. All file:line references were verified against source.

---

## 0. Where the project stands today

**Strengths (lead with these — genuinely unusual for a hackathon build):**

- Clean five-layer separation (simulation → detection → policy → execution → audit), each
  layer testable in isolation.
- Guardrails are pure deterministic code (`backend/app/policy/guardrails.py`), not prompt
  instructions — exhaustively unit-tested including boundary values. This is the single
  strongest technical talking point in the repo.
- A real information barrier: the hidden recoverability model (`simulation/recoverability.py`)
  is imported by exactly one module (`execution/connectors.py`), so recovery numbers genuinely
  test agent reasoning rather than peeking at answers.
- Regression tests tied to real observed bugs (audit timestamp collisions, stale
  `next_action_at`), seed-guaranteed demo scenarios, honest documentation of weaknesses.

**Weaknesses, ranked by likelihood of hurting during judging:**

| # | Risk | Where | Why it matters on demo day |
|---|---|---|---|
| 1 | Gemini free-tier burst limits mid-batch; fail-safe silently converts those cases into `escalated_human` | no retry/backoff anywhere in `backend/app` (grep-verified) | Headline recovery rate can collapse live on stage |
| 2 | `POST /batches/run` runs the whole pipeline synchronously inside the HTTP request | `api/batches.py` trigger_batch_run | Browser fetch can time out; UI shows only "Running…" with zero feedback |
| 3 | Dashboard never refreshes after load | `dashboard/page.tsx` useBatchData (one-shot fetch) | Judges can see stale numbers after background processing / due-job runs |
| 4 | Sim-clock vs wall-clock mixing discards the LLM's chosen retry date in instant mode | `policy/proposer.py:112` uses real `datetime.now()` while runner advances `sim_now` days ahead | Correctness smell for expert judges; masked only because guardrails self-heal |
| 5 | Missing indexes on the highest-read FK columns | `attempts.case_id` (models.py:85), `audit_events.case_id` (models.py:101) | Case drill-down degrades first as data grows |
| 6 | Zero logging/observability | grep confirms no `logging` usage in `backend/app` | Diagnosing a live-demo hiccup means reading audit payloads in psql |

---

## 1. Winning-the-hackathon moves (highest demo ROI first)

Judges reward three things: a **"watch it think" live moment**, **proof the hard parts
(guardrails) actually fire**, and a credible answer to **"would this work in production?"**

### 1.1 Live batch progress (P0 — biggest single upgrade)

Today the pipeline blocks inside the request (`api/batches.py`) and `/run` shows a static
label (`run/page.tsx:99`). Change to:

1. `POST /batches/run` returns `{batch_id}` immediately; the pipeline runs as a FastAPI
   `BackgroundTask` (no new infra needed), updating progress on a new `batches` table row
   (`cases_done / cases_total / phase`).
2. New `GET /batches/{id}/progress`; `/run` and `/dashboard` poll it every ~1s while running.
3. Stretch: stream per-case decision events over SSE so judges watch root cause → proposed
   action → guardrail verdict appear case-by-case.

Why it wins: the current demo asks judges to trust a summary that appears after a silent wait.
A ticking "case 14/20 · insufficient_funds · retry_scheduled · compliance: PASS" feed makes the
agent feel alive and doubles as proof there is no sleight of hand.

### 1.2 Make Gemini calls bulletproof (P0 — protects your headline number)

Known issue (documented in CLAUDE.md): bursts trip free-tier RPM limits and the fail-safe turns
rate-limited cases into `escalated_human`, deflating recovery rate. Fix cheaply:

- Client-side token-bucket rate limiter (~10 req/min) around all Gemini calls + exponential
  backoff with jitter on `APIError` (use `tenacity` or ~30 lines of hand-rolled retry).
- Catch broader transport exceptions (timeouts, connection resets) in `llm_classifier.py`,
  `proposer.py`, `voice.py` — currently only `google.genai.errors.APIError` is caught.
- Cache classification results keyed on `(raw_failure_reason)` — identical decline messages
  recur constantly in synthetic data; this alone removes most LLM calls per batch.
- Log every LLM call: latency, success/fallback, cache hit. Feeds §1.4.

### 1.3 Voice playback in the browser (P0 effort, stretch-goal payoff)

Sarvam TTS was deferred — you don't need it. Use the Web Speech API (`speechSynthesis`) on the
existing transcript in `cases/[id]/page.tsx`: render the transcript as chat bubbles
(agent vs customer) and add a play button speaking agent turns with a `hi-IN` voice when
available. Zero backend work, zero API cost, delivers the PRD §10 stretch moment ("hear the
Hinglish recovery call") during judging. Fallback gracefully to text if no Hindi voice exists.

Also upgrade the transcript rendering from `<pre>` to chat bubbles with speaker labels — much
stronger visually.

### 1.4 "Agent reasoning" panel + guardrail-intervention feed (P1)

The audit data already contains everything needed for the most persuasive screen in the app:

- On the dashboard: a "Guardrails in action" feed listing recent `stopped` /
  `compliance_check(substituted=true)` events with rule name + one-line reason, linking to
  each case. Turns two counters into visible stories.
- On the case page: a highlighted "Why this action?" card pulling the LLM rationale +
  guardrail verdict from existing event payloads. This is the first question every judge asks;
  answer it before they ask.

### 1.5 Recovery-over-time chart (P1)

One dependency-free inline-SVG chart on the dashboard: cumulative ₹ recovered across batch
rounds (data derivable from attempts/outcome events). A rising curve beats four stat tiles.
Keep it monochrome accent per the existing design system.

### 1.6 One-click demo mode (P1)

A "Run demo batch" button that fires the guaranteed-cases batch with a known seed and lands on
a scripted tour (the drill-downs from PRD §15). Removes all live-demo risk from seed choice,
rate limits, and navigation fumbling. Cheap: preset form values + query params.

---

## 2. Backend: correctness fixes (P0 — small, do before submission)

1. **Sim-clock leak** — `policy/proposer.py:112` builds `retry_date` from real wall clock.
   Thread the runner's `sim_now` through `decide_action` into `propose_action` so LLM-chosen
   retry offsets land on the simulated timeline instead of being silently discarded (and
   re-derived by the guardrail's pre-debit correction).
2. **Uncommitted audit events on `no_action` rounds** — `execution/runner.py` `_run_case_round`
   returns from the no_action branch without committing; events stay pending in the session and
   are lost if anything fails before a later commit. Commit (or flush+commit at branch end)
   there like the other branches do.
3. **Naive datetime defaults** — `models.py:54` (`Case.created_at`) and `models.py:86`
   (`Attempt.timestamp`) use deprecated Python-side `datetime.utcnow`, writing naive datetimes
   into `timezone=True` columns. Switch both to `server_default=func.now()` — you already did
   exactly this for `AuditEvent` and `Ticket` after the timestamp-collision bug; finish the job
   (one migration + model change).
4. **Missing indexes migration** — add `attempts.case_id`, `audit_events.case_id`,
   `audit_events.event_type`, `cases.status`, `cases.created_at`. These back every timeline
   read, rollup join, and list ordering; audit_events is your fastest-growing table (~3 events
   × up to 6 rounds per case).
5. **Kill N+1 loads in the runner** — `runner.py` lazy-loads `case.customer` and
   `case.attempts` per case; use `selectinload(Case.customer, Case.attempts)` in the batch
   fetch query. Also fix the same pattern in `scripts/run_detection.py`.
6. **Input bounds server-side** — cap `n_cases` (e.g. ≤500) in `RunBatchRequest`; cap the
   `limit` param in `GET /cases` (≤500); validate `status`/`type` filters against
   `app/constants.py`; paginate `GET /tickets`. The frontend already caps at 500
   (`run/page.tsx:58`), but the API must not trust it.
7. **Batch-scoped `summarize()`** — `runner.py summarize()` aggregates the entire cases table,
   so CLI scripts print cumulative numbers while the API recomputes scoped ones. Scope it by
   `batch_id` (or delete it and always call `audit/rollup.batch_summary`) to kill the
   two-summaries footgun documented in CLAUDE.md.

## 3. Backend: robustness & observability (P1)

1. **Structured logging** — stdlib `logging` with JSON formatter is enough for this scope:
   request-id middleware, one line per pipeline step per case (detection path taken, policy
   decision, guardrail verdict, LLM latency/fallback). This converts "check psql payloads" into
   readable logs during debugging and demos.
2. **Health check that checks** — `/health` (`api/main.py:47`) returns a static dict. Ping the
   DB (`SELECT 1`) and report Gemini config presence; useful when something is misconfigured
   right before a demo.
3. **Fail-fast on missing `GEMINI_API_KEY`** — `config.py` defaults it to `""` and the client
   is built lazily, so a missing key surfaces as an opaque mid-request error. Validate at
   startup (except when explicitly disabled for tests).
4. **Idempotency on mutations** — accept an optional `Idempotency-Key` header on
   `POST /batches/run` so double-clicks don't create duplicate batches (today every click runs
   a full new pipeline synchronously).
5. **Atomic due-case claiming** — `process_due_cases` does select-then-act; two concurrent
   invocations double-process cases. Claim atomically:
   `UPDATE cases SET next_action_at = NULL WHERE next_action_at <= now() RETURNING ...`
   (or `FOR UPDATE SKIP LOCKED`).
6. **Test DB isolation** — no `conftest.py` exists; DB-backed tests commit into the dev
   Postgres (documented). Add a `conftest.py` fixture that runs each test in a transaction and
   rolls back, or points tests at a second docker-compose database. Removes the
   "row counts include history" caveat permanently and makes parallel pytest safe.
7. **Architecture-invariant test** — the recoverability import barrier is enforced only by
   comment. Add a two-line test asserting `app.detection.*` and `app.policy.*` never import
   `app.simulation.recoverability`.

## 4. Frontend improvements

Current state: hand-rolled `fetch` client (`lib/api.ts`), one-shot data fetching everywhere,
good dark design system, decent loading/error states, zero polling. Prioritized:

1. **Polling layer (P0)** — one tiny hook (`use-poll.ts`, setInterval + cleanup) reused by
   `/run`, `/dashboard`, and `ScheduledActionsPanel`; poll while a batch is non-terminal or a
   scheduled panel has rows. Don't add react-query/SWR just for this — the app has only five
   fetch sites and zero deps beyond Next/React/Tailwind; keep it that way.
2. **Chat-bubble transcripts + speech (P0)** — see §1.3. Highest visual payoff per line of code.
3. **Guardrails feed + rationale card (P1)** — see §1.4.
4. **Recovery chart (P1)** — see §1.5.
5. **Interleave attempts into the timeline (P1)** — `/cases/[id]` renders AuditEvents and
   Attempts as two separate sections; merge them chronologically into the Sentry-style
   timeline so the story reads top-to-bottom in one pass.
6. **Skeleton loaders (P2)** — replace "Loading…" text on dashboard/case pages with pulse
   placeholders matching final layout; avoids layout shift on stage.
7. **A11y pass (P2)** — icon-only links need `aria-label`s (e.g. scheduled-actions row arrow);
   filter chips are `<button>`s (good); verify focus-visible rings survived the Tailwind v4
   theme tokens; check status colors against contrast rules already documented in CLAUDE.md's
   design-system section.
8. **Money formatting consistency (P2)** — amounts arrive as floats; large sums can show cent
   drift. Either serialize Decimal-as-string in API responses or format with
   `maximumFractionDigits: 0` consistently (case page currently shows 2 decimals).

## 5. Scalability: what breaks past demo scale

Ordered by the load point where it bites:

| Scale | First thing to break | Fix |
|---|---|---|
| ~50 concurrent batches | Sync pipeline inside HTTP workers | Background task today → dedicated worker queue (arq/Celery/Temporal) later |
| 100k+ cases | Serial per-case loops; detection/policy are embarrassingly parallel | Batch cases into worker pools; batch LLM calls (one call classifying N decline messages) |
| 10M+ audit_events | Timeline queries + table bloat | Indexes (§2.4), monthly partitioning on `timestamp`, archive cold events to object storage |
| Multi-instance deploy | Module-level Gemini singleton fine, but in-process rate limiter/cache aren't shared | Move limiter to Redis; cache classification in Postgres/Redis keyed on message hash |
| Real traffic spikes | No per-tenant quotas | Per-merchant API keys with independent rate limits |
| Long recovery journeys | Sim-clock concept disappears in prod; `next_action_at` scheduling becomes the real scheduler | Keep `next_action_at`; replace manual `/jobs/run-due` with cron + the atomic claim from §3.5 |

Also worth stating publicly (judges ask): the hidden recoverability model validates *plumbing*,
not strategy. The production analogue is replaying historical outcomes to evaluate policy
changes offline before shipping them — say this in Q&A and it turns the biggest architectural
criticism into a strength.

## 6. Real-world implementation roadmap (the "how would this ship?" answer)

Each simulation boundary maps to a concrete integration. This table is essentially your
architecture slide:

| Mock boundary (file) | Production integration | Effort |
|---|---|---|
| Recoverability RNG rolls (`simulation/recoverability.py`) | Disappears — outcomes arrive via **Razorpay payment/retry webhooks**; requires webhook ingestion endpoint + verification | Medium |
| Decline-code corpus (`simulation/generator.py`) | Live failure feed from Razorpay APIs/webhooks; map real gateway code sets into `detection/rules.py` regex table | Low-Med |
| SMS/WhatsApp labels (`policy/channels.py`, `execution/connectors.py`) | MSG91/Gupshup provider clients + delivery-receipt webhooks updating Attempt outcomes | Medium |
| Payment links (`send_update_link`) | Razorpay Payment Links API + conversion webhooks | Low |
| Text-only voice roleplay (`execution/voice.py`) | Exotel/Knowlarity dialer + ASR/TTS; extraction prompt stays identical — it consumes transcripts either way | High |
| DND boolean (`customers.dnd_registered`) | NCPR/DND registry sync or merchant preference service lookup | Medium |
| In-house tickets (`execution/tickets.py`) | Zendesk/Freshdesk outbound client with retry + idempotency | Low |
| Manual `/jobs/run-due` (`api/jobs.py`) | Celery beat / cloud scheduler + SKIP LOCKED claiming (§3.5) | Low |
| No auth (`api/main.py`) | OIDC/API keys per merchant; tenancy moves from column scoping to token claims | Medium |

Sequencing for a real deployment: (1) webhook ingestion first — everything else keys off
real outcomes; (2) one channel provider end-to-end (SMS) to prove the connector contract;
(3) queue-based execution; (4) auth; (5) voice. The current layer boundaries survive all five
steps unchanged — that is the strongest real-world argument the codebase can make, and it's
worth a slide.

## 7. Suggested order of attack (9 days, solo)

| Days | Items |
|---|---|
| 1–2 | §2 correctness fixes (all small) + §1.2 rate limiting/backoff/caching |
| 3–4 | §1.1 background batches + progress polling (backend + frontend hook) |
| 5 | §1.3 transcript chat bubbles + browser TTS; §4.5 interleaved timeline |
| 6 | §1.4 guardrail feed + rationale card; §1.5 recovery chart |
| 7 | §1.6 demo mode; full demo rehearsal; fix whatever rehearsal exposes |
| 8–9 | Buffer + submission assets (README/architecture diagram from §6 table) |

If time compresses, protect in this order: §1.2 (protects the number) > §2.1–2.4 (cheap
correctness) > §1.1 (live feel) > §1.3 (wow moment) > everything else.


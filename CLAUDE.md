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
| 3 | Policy engine (proposal + guardrails) | Not started |
| 4 | Execution layer + batch runner | Not started |
| 5 | Voice recovery channel | Not started |
| 6 | B2B receivables flow | Not started |
| 7 | Audit trail storage + dashboard API | Not started |
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

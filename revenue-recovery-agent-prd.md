# PRD: AI Revenue Recovery Agent
**Razorpay Buildathon — Track 03: AI Revenue Recovery**
Owner: Dewashish | Submission deadline: Sept 3, 2026 | Build start: Aug 22, 2026

---

## 1. Problem statement

Revenue leaks out of a business through disconnected failure points: failed card/UPI debits, failed subscription mandates, and overdue B2B invoices. Each is currently handled reactively, generically, and without a record of what was tried or why. This project builds a single agent that:

1. **Detects** revenue at risk across three leak types (payment/mandate failures, B2B receivables)
2. **Diagnoses** root cause per case
3. **Chooses** a bounded recovery action from a fixed action space, across escalating channels (nudge → SMS/email → voice → human)
4. **Executes** the action against a simulated environment and observes outcome
5. **Reports** measured recovery (₹ at risk vs ₹ recovered) with a full audit trail and enforced compliance/stopping rules

This is not a real Razorpay integration. Everything runs against a synthetic environment with a hidden recoverability model, since the goal is to prove the reasoning + guardrail + measurement loop, not real payment processing.

## 2. Goals

- Show a believable, measured recovery number on a batch (e.g. "₹X at risk → ₹Y recovered, Z% recovery rate") that updates live during a demo
- Show root-cause-specific reasoning, not one-size-fits-all retry logic
- Show hard-coded (not LLM-discretionary) stopping rules and compliance checks
- Show a full audit trail, drillable per case
- Cover 2 distinct revenue-leak types (payment/mandate failure + B2B receivables) to prove generality
- Include a voice recovery channel (Hinglish, simulated) as the escalation channel for high-value/unresponsive cases

## 3. Non-goals (explicitly out of scope)

- Real Razorpay API integration (simulated data only, per decision)
- Real telephony/live calls (simulated transcript + optional TTS render, not a live phone system)
- Real customer PII or real transaction data
- Full checkout drop-off / cart abandonment flow (dropped to protect scope — can be a "future work" slide, not built)
- Multi-tenant/production auth, billing, scaling concerns

## 4. Track requirement → feature mapping

| Track requirement | Where it's covered |
|---|---|
| Detects revenue at risk | Detection layer (§7) |
| Determines the right intervention | Policy engine (§8) |
| Executes a bounded recovery workflow | Execution layer + channel ladder (§9) |
| Payment failures | Payment/mandate leak type |
| Overdue receivables | B2B receivables leak type |
| Hinglish voice recovery | Voice channel (§10) |
| Promise-to-pay tracker | Outcome field on B2B + voice interactions |
| Measured money recovered across a batch | Batch run + dashboard (§12) |
| Compliant escalation | RBI e-mandate + DND-inspired rules (§9.3) |
| Stopping rules | Hard-coded caps in policy engine (§9.2) |
| Audit trail | Structured event log (§11) |

## 5. System architecture

```
┌─────────────────────────┐
│ Synthetic Environment    │  generates batch: transactions, mandates,
│ Generator                │  invoices, customers, hidden recoverability model
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ Detection Layer           │  rules + LLM classify root cause per case
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ Policy Engine             │  LLM proposes action → code enforces
│ (LLM + hard guardrails)   │  stopping rules + compliance before allowing it
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ Execution Layer           │  channel connectors (nudge/SMS/email/voice/human)
│ (mock connectors)         │  apply action to simulated env, get outcome
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ Audit Trail + Dashboard   │  every decision logged; batch rollup;
│                           │  drill-down per case                      
└───────────────────────────┘
```

Tech stack:
- **Backend**: FastAPI (Python) — orchestration, policy engine, simulation
- **DB**: Supabase/Postgres — cases, events, audit log, batch runs
- **LLM**: Claude API (Sonnet) for root-cause reasoning, policy proposal, voice transcript generation
- **Frontend**: Next.js — dashboard, batch runner, audit drill-down, case timeline
- **Voice (stretch)**: Sarvam TTS for Hinglish audio render of transcript

## 6. Data model

### Case (base entity, one of three types)
```
Case {
  id: uuid
  type: "payment_failure" | "mandate_failure" | "receivable"
  customer_id: uuid
  amount: decimal
  currency: "INR"
  created_at, due_at (for receivables)
  status: "open" | "recovering" | "recovered" | "written_off" | "escalated_human"
  raw_failure_reason: string | null   # gateway/bank message, receivables = null
  root_cause: enum | null             # filled by detection layer
  attempts: [Attempt]                 # history of actions taken
  outcome: "recovered" | "unrecovered" | "pending"
  recovered_amount: decimal
}
```

### Customer (synthetic persona)
```
Customer {
  id: uuid
  dnd_registered: bool
  responsiveness_profile: "cooperative" | "evasive" | "unresponsive" | "hostile"
  preferred_channel: "sms" | "email" | "voice" | "whatsapp"
  card_on_file_status: "valid" | "expired" | "insufficient_funds_pattern"
}
```

### Attempt (one action taken on a case)
```
Attempt {
  id, case_id, timestamp
  channel: "silent_retry" | "sms_nudge" | "email_link" | "voice_call" | "human_escalation"
  action: enum from bounded action space (§9)
  compliance_check: { passed: bool, rule: string, reason: string }
  outcome: "success" | "failure" | "no_response" | "opt_out" | "promise_to_pay"
  promise_to_pay_date: date | null
  transcript: string | null   # for voice_call
}
```

### AuditEvent (append-only, drives §11)
```
AuditEvent {
  id, case_id, attempt_id | null, timestamp
  event_type: "detected" | "diagnosed" | "action_proposed" | "compliance_check" |
              "action_executed" | "outcome_recorded" | "stopped" | "escalated"
  actor: "system" | "llm" | "human"
  payload: jsonb   # full reasoning/decision detail
}
```

## 7. Root cause taxonomy

**Payment/mandate failures:**
| Root cause | Typical recovery approach |
|---|---|
| `insufficient_funds` | Scheduled retry (payday-aligned), 2–3 attempts, spaced |
| `card_expired` | Send update-payment-method link, no blind retry |
| `issuer_declined` | Single retry, then escalate channel (won't self-resolve) |
| `bank_timeout` | Immediate single retry (likely transient) |
| `fraud_suspected` | No auto-retry, escalate to human immediately |
| `mandate_revoked` | No retry, requires new mandate setup, notify + link |

**B2B receivables:**
| Root cause | Typical recovery approach |
|---|---|
| `overdue_early` (0–15 days) | Gentle reminder, low urgency |
| `overdue_mid` (16–45 days) | Reminder + promise-to-pay request |
| `overdue_late` (45+ days) | Escalating reminder + voice call + human handoff |
| `disputed` | No auto-chase, route to human immediately |

Detection layer: deterministic mapping where the failure code is unambiguous (bank decline codes); LLM classification where it's free-text or requires context (dispute flags, gateway messages, invoice notes).

## 8. Bounded action space

Fixed, enumerable set — the LLM **selects from** this list, it never generates a free-form action:

```
ACTIONS = [
  "no_action",
  "retry_now",
  "retry_scheduled",       # requires: retry_date
  "send_update_link",
  "send_reminder",          # requires: tone (gentle|firm)
  "request_promise_to_pay",
  "voice_call",
  "escalate_human",
  "stop_case"               # terminal, requires: reason
]
```

Each `Case.type` has an allowed subset (e.g. `send_update_link` is invalid for a receivable). The policy engine's LLM call returns a structured JSON pick from the allowed subset with a rationale string — this rationale is what gets stored in the audit trail, not free prose.

## 9. Policy engine

### 9.1 Flow
1. Given `Case` + `Attempt history` + `Customer` → LLM proposes `{action, params, rationale}`
2. Code-level guardrail layer validates the proposal against stopping rules + compliance rules
3. If rejected → engine substitutes the nearest compliant fallback (e.g. voice_call blocked by DND → falls back to send_reminder) and logs both the rejection and the substitution
4. If approved → passed to execution layer

**Guardrails are code, not prompt instructions.** The LLM proposes; a deterministic function approves/rejects/rewrites. This is the detail to highlight in the demo — an LLM "agreeing" to respect a limit is not the same as a system that structurally cannot violate it.

### 9.2 Stopping rules (hard-coded)
- Max 3 retry attempts per case, minimum 24h apart
- Max 4 total contact attempts across all channels per case (any type)
- No same-channel contact twice within 24h
- If `fraud_suspected` or `disputed` → auto-escalate to human on detection, skip all retry/nudge logic
- If case unresolved after N days (configurable, e.g. 14) → auto-escalate to human, mark case `escalated_human`
- Every case terminates in one of: `recovered`, `written_off`, `escalated_human` — no case stays in limbo past the batch window

### 9.3 Compliance rules (hard-coded, RBI/TRAI-inspired for demo realism)
- **Pre-debit notification**: any `retry_scheduled` action must have a corresponding notification event logged ≥24h before the retry timestamp (models RBI's 2026 e-mandate pre-debit notification requirement)
- **Post-debit confirmation**: every successful retry logs a confirmation event
- **DND respect**: if `customer.dnd_registered == true`, `voice_call` is not a valid proposal — auto-falls back to SMS/email
- **Calling hours**: `voice_call` only valid within a configured window (e.g. 9am–7pm IST)
- **Opt-out honored**: if any prior attempt outcome was `opt_out`, no further contact attempts on that case except the required post-transaction ones

## 10. Voice recovery channel (Hinglish, simulated)

**MVP (build this):** text-based simulated call. Two LLM roles in a scripted exchange:
- **Recovery agent role**: explains the failure in Hinglish, offers 2–3 concrete next steps (retry now / send link / reschedule), asks for confirmation
- **Synthetic customer role**: responds according to `Customer.responsiveness_profile` (cooperative agrees quickly, evasive stalls/asks questions, unresponsive gives short non-answers, hostile pushes back)
- Conversation runs for a capped number of turns (e.g. 6), then an extraction step parses the transcript into a structured outcome: `{consent: bool, action: retry_now|send_link|promise_to_pay, promise_to_pay_date}`
- Full transcript + extracted outcome stored on the `Attempt`

**Stretch (only after core is solid):** render the agent's turns as Hinglish audio via Sarvam TTS for a live demo moment. Does not change any underlying logic — purely a presentation layer on top of the transcript already being generated.

## 11. Audit trail requirements

Every case must be drillable to a full timeline: detected → diagnosed (with root cause + confidence) → action proposed (with LLM rationale) → compliance check (pass/fail/substituted, with rule cited) → executed → outcome. No step is inferred after the fact — each is a persisted `AuditEvent` written at the time it happens.

Dashboard must show, per batch run:
- Total ₹ at risk
- Total ₹ recovered
- Recovery rate overall and broken down by root cause
- Count of stopping-rule triggers (proof guardrails fired, not just existed)
- Count of compliance substitutions (proof compliance logic actually changed behavior at least once — seed the synthetic data to guarantee this happens)

## 12. Synthetic environment + recoverability model

Generator produces a configurable batch (default: ~150–300 cases, mixed types) with:
- Realistic root-cause distribution (weight `insufficient_funds` and `card_expired` heavily, others as long tail)
- A **hidden** recoverability function per root cause × action × channel × customer profile, e.g.:
  - `insufficient_funds` + `retry_scheduled` (3+ days later) + cooperative customer → 55–65% success
  - `card_expired` + `send_update_link` → 70–80% success if link is "clicked" (roll separately), else 0%
  - `fraud_suspected` → 0% auto-recovery regardless of action (must go to human)
  - `overdue_mid` receivable + `request_promise_to_pay` + cooperative → 50% gives a real promise-to-pay date, of which 70% honor it
- This hidden model is what the execution layer "rolls against" to produce outcomes — the agent never sees the model directly, only the outcome, so its behavior over a batch is a genuine test of the policy logic

## 13. Repo structure (suggested, for Claude Code handoff)

```
/backend
  /app
    /simulation      # environment generator, recoverability model
    /detection        # root cause classifiers (rules + LLM)
    /policy            # action proposal + guardrail enforcement
    /execution         # channel connectors (mock), voice conversation runner
    /audit             # event logging, batch rollup queries
    /api                # FastAPI routes: run batch, get case, get audit trail
  /tests
/frontend
  /app
    /dashboard          # batch summary, recovery metrics
    /cases/[id]         # case timeline / audit drill-down
    /run                # trigger a new batch run
/prd.md                  # this file
```

## 14. Build plan (12 days, solo)

| Days | Milestone |
|---|---|
| 1–2 | Synthetic environment generator + data models + seed script |
| 3–4 | Detection layer (rules + LLM root-cause classification) |
| 5–6 | Policy engine: LLM proposal + hard-coded guardrails (stopping rules + compliance) |
| 7 | Execution layer: mock connectors for retry/link/reminder, wire to recoverability model |
| 8 | Voice channel: scripted two-role LLM conversation + outcome extraction |
| 9 | B2B receivables flow (reuses policy engine, new action subset + root causes) |
| 10 | Audit trail storage + batch rollup queries + dashboard (Next.js) |
| 11 | Case timeline/drill-down UI, polish numbers, seed data to guarantee good demo stats |
| 12 | Buffer, demo script rehearsal, submission |

## 15. Demo script (what to show judges)

1. Trigger a batch run live (or pre-run + replay) — ~200 cases across payment failures, mandate failures, receivables
2. Show dashboard: ₹ at risk → ₹ recovered → recovery rate, broken down by root cause
3. Drill into one `insufficient_funds` case: detection → scheduled retry → pre-debit notification event → success
4. Drill into one `card_expired` case that got a link instead of a blind retry — show the reasoning
5. Drill into one case where a stopping rule fired (e.g. hit max attempts → auto-escalated to human) — prove guardrails aren't decorative
6. Drill into one case where DND blocked a voice call and it fell back to SMS — prove compliance logic actually changes behavior
7. Play/show one voice recovery transcript (Hinglish), highlight the extracted structured outcome
8. Close on the audit trail for one case end-to-end, unbroken

## 16. Open risks / questions

- LLM cost/latency at batch scale (200+ cases × multiple LLM calls each) — may need to cache/batch classifier calls or use a cheaper model for root-cause classification vs policy reasoning
- Need to seed synthetic data deliberately so demo always includes at least one of each "guardrail fired" case — don't rely on random generation alone
- Decide before Day 5: does root-cause detection use one LLM call per case, or a cheaper rules-first-then-LLM-fallback approach (recommended, for cost + speed)

"""Voice recovery channel, MVP per PRD §10: a scripted, capped-turn,
text-based conversation between two Gemini-played roles (recovery agent,
synthetic customer), then an extraction step that parses the transcript
into a structured outcome. TTS rendering is explicitly out of scope.

The conversation is a presentation/audit-trail layer, not the source of
truth for whether money actually gets recovered - that's still the hidden
recoverability model (app/simulation/recoverability.py), rolled the same
way as every other channel in app/execution/connectors.py. The extracted
{consent, action, promise_to_pay_date} only shapes *how* the outcome is
labeled (e.g. "promise_to_pay" vs generic "success"/"failure"), consistent
with how every other channel already works.
"""
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from google.genai import errors

from app.config import settings
from app.detection.gemini_client import get_client
from app.llm_resilience import call_with_resilience

MAX_TURNS = 6  # PRD §10: "capped number of turns (e.g. 6)"

RESPONSIVENESS_BEHAVIOR: dict[str, str] = {
    "cooperative": "You agree readily once the option is explained. You ask at most one clarifying question, then agree to a specific option within 1-2 replies.",
    "evasive": "You stall - you ask questions, bring up other topics, say you'll 'check and get back', and avoid giving a clear yes/no for as long as possible.",
    "unresponsive": "You give short, low-effort, non-committal replies ('hmm', 'ok', 'not sure', 'maybe later') and never clearly commit to anything.",
    "hostile": "You are irritated and pushy - you push back on the agent, question why you're being contacted, and are reluctant to agree to anything.",
}

AGENT_SYSTEM_PROMPT = """You are a recovery agent for an Indian fintech, speaking Hinglish (a natural mix of Hindi and English, written in Latin script, like real Indian customer support calls) to a customer about a failed payment.

Case: {case_type}, root cause: {root_cause}, amount: INR {amount}.

Your job in this call:
1. Politely explain that a payment failed and why, in plain terms.
2. Offer 2-3 concrete next steps (for example: retry now, send a payment link, reschedule/promise a payment date) appropriate to the failure reason.
3. Ask the customer to confirm one option.
4. Once they give a clear answer (or after a few exchanges if they won't commit), politely close the call.

Conversation so far:
{transcript}

Write ONLY your next line of dialogue as the agent (1-3 sentences, Hinglish, no labels like "Agent:", no stage directions). If the customer has already given a clear answer, close the call politely instead of repeating the pitch.
"""

CUSTOMER_SYSTEM_PROMPT = """You are a bank customer receiving a call about a failed payment of INR {amount} (reason: {root_cause}). {behavior}

Reply in Hinglish (Hindi+English mix, Latin script), like a real Indian customer on a call.

Conversation so far:
{transcript}

Write ONLY your next line of dialogue as the customer (1-2 sentences, Hinglish, no labels like "Customer:", no stage directions).
"""

EXTRACTION_PROMPT = """Read this recovery call transcript and extract the outcome.

Transcript:
{transcript}

Respond with ONLY a JSON object, no markdown fences, in this exact shape:
{{"consent": <true if the customer clearly agreed to a specific next step, else false>, "action": "<one of: retry_now, send_link, promise_to_pay, none>", "promise_to_pay_date_offset_days": <int, only meaningful if action is promise_to_pay, else 0>}}
"""

FALLBACK_EXTRACTION = {"consent": False, "action": "none", "promise_to_pay_date": None}


def _format_transcript(turns: list[dict]) -> str:
    if not turns:
        return "(call not yet started)"
    return "\n".join(f"{t['role'].capitalize()}: {t['text']}" for t in turns)


def _generate_turn(prompt: str, client: Any) -> str:
    # Transient errors are retried with backoff inside call_with_resilience;
    # exhausted retries re-raise and run_conversation keeps the partial
    # transcript, same as before - just without dropping a turn to one 429.
    response = call_with_resilience(lambda: client.models.generate_content(model=settings.gemini_model, contents=prompt))
    text = (response.text or "").strip()
    return text or "..."


def run_conversation(case, customer, client: Any = None, max_turns: int = MAX_TURNS) -> list[dict]:
    """Runs the scripted two-role conversation and returns the turn list:
    [{"role": "agent"|"customer", "text": "..."}]. Fails safe to a short,
    inconclusive transcript if Gemini is unreachable/rate-limited.
    """
    client = client or get_client()
    behavior = RESPONSIVENESS_BEHAVIOR.get(customer.responsiveness_profile, RESPONSIVENESS_BEHAVIOR["unresponsive"])
    turns: list[dict] = []

    try:
        for i in range(max_turns):
            transcript_so_far = _format_transcript(turns)
            if i % 2 == 0:
                prompt = AGENT_SYSTEM_PROMPT.format(
                    case_type=case.type, root_cause=case.root_cause, amount=case.amount, transcript=transcript_so_far
                )
                text = _generate_turn(prompt, client)
                turns.append({"role": "agent", "text": text})
            else:
                prompt = CUSTOMER_SYSTEM_PROMPT.format(
                    amount=case.amount, root_cause=case.root_cause, behavior=behavior, transcript=transcript_so_far
                )
                text = _generate_turn(prompt, client)
                turns.append({"role": "customer", "text": text})
    except (errors.APIError, OSError):
        if not turns:
            turns.append({"role": "agent", "text": "(call could not be connected - service unavailable)"})

    return turns


def extract_outcome(turns: list[dict], client: Any = None, now: datetime | None = None) -> dict:
    """Parses the transcript into {consent, action, promise_to_pay_date}.
    Fails safe to FALLBACK_EXTRACTION on any parse/API failure.
    """
    client = client or get_client()
    now = now or datetime.now()
    transcript = _format_transcript(turns)
    prompt = EXTRACTION_PROMPT.format(transcript=transcript)

    try:
        response = call_with_resilience(
            lambda: client.models.generate_content(model=settings.gemini_model, contents=prompt)
        )
    except (errors.APIError, OSError):
        return dict(FALLBACK_EXTRACTION)

    return _parse_extraction(response.text or "", now)


def _parse_extraction(text: str, now: datetime) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return dict(FALLBACK_EXTRACTION)

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return dict(FALLBACK_EXTRACTION)

    consent = bool(data.get("consent", False))
    action = data.get("action")
    if action not in ("retry_now", "send_link", "promise_to_pay", "none"):
        action = "none"

    promise_to_pay_date: date | None = None
    if action == "promise_to_pay":
        try:
            offset_days = int(data.get("promise_to_pay_date_offset_days", 5))
        except (TypeError, ValueError):
            offset_days = 5
        offset_days = max(offset_days, 1)
        promise_to_pay_date = (now + timedelta(days=offset_days)).date()

    return {"consent": consent, "action": action, "promise_to_pay_date": promise_to_pay_date}


def format_transcript_for_storage(turns: list[dict]) -> str:
    return _format_transcript(turns)

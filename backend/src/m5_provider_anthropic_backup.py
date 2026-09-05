"""
M5 provider abstraction (M9).

M8 root cause (see M9_CHANGELOG.md for the full writeup): the M6 dev/
holdout runner (scripts/run_m6.py::try_load_m5_engine) hardcoded
``MockProvider()`` with no ``mock_response``. ``MockProvider.reason``
then executed ``AIDecision(**self.mock_response)`` with
``self.mock_response is None``, which raises ``TypeError`` on every
single call. ``M5ReasoningEngine.evaluate_payment`` catches that as a
generic provider failure and returns ``ESCALATE`` - so M5 "ran" on every
eligible case, but could never once produce a successful decision. M6's
independent AI-recommendation validation then correctly rejected the
resulting ``None`` decision every time (see ``RULE_M6_AI_RECOMMENDATION_
REJECTED`` / ``AI_NO_DECISION`` in the dev audit log) - which is why this
was safe (no bad financial decision ever resulted) but was also useless
(M5 provided zero genuine value).

This module fixes the *wiring*, not by hardcoding a working mock in its
place, but by replacing "always instantiate MockProvider()" with real
dependency injection:

    ReasoningProvider              - the abstract interface M5 depends on
    |-- RealLLMProvider            - production: calls an actual LLM API
    |-- MockProvider               - tests only: returns a caller-supplied,
    |                                 schema-validated canned response
    `-- FailingProvider            - tests only: always raises, for
                                      exercising M5/M6's failure paths

    build_provider()               - the only place that decides which
                                      concrete provider a pipeline run
                                      gets, based on environment
                                      configuration. Returns ``None``
                                      (not a MockProvider) when no real
                                      provider is configured - callers
                                      (scripts/run_m6.py) then run without
                                      M5 rather than silently fabricating
                                      "AI" output. This is the one
                                      behavioral choice this file makes
                                      on its own: never invent a
                                      successful-looking response when
                                      there is nothing real behind it.
"""

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional

from src.m5_schema import AIDecision


class ReasoningProvider(ABC):
    """Everything M5 needs from an AI backend: turn bounded, ground-truth-
    free evidence into a schema-validated :class:`AIDecision`, or raise.
    ``M5ReasoningEngine`` never knows or cares which concrete provider is
    behind this interface."""

    @abstractmethod
    def reason(self, case_evidence: dict) -> AIDecision:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Production provider
# ---------------------------------------------------------------------------

_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
_DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_SYSTEM_PROMPT = (
    "You are a bounded financial reconciliation reasoning assistant. You are "
    "given ONE payment that a deterministic matching engine could not "
    "confidently resolve, plus a short list of candidate settlements the "
    "engine already generated deterministically, each with its own "
    "amount/date/reference evidence. You do not have access to ground truth "
    "and must not guess. Respond with ONLY a single JSON object (no prose, "
    "no markdown fences) with exactly these fields: "
    '{"decision": "MATCH" | "NO_MATCH" | "AMBIGUOUS", '
    '"selected_candidate_id": string or null, '
    '"confidence": number between 0.0 and 1.0, '
    '"reasoning": short string, '
    '"missing_evidence": array of short strings (may be empty), '
    '"recommended_action": "ACCEPT" | "ESCALATE" | "REQUEST_MORE_DATA"}. '
    "selected_candidate_id MUST be one of the supplied candidate settlement "
    "IDs, or null. Never invent an ID. If no candidate is clearly and "
    "safely correct, return AMBIGUOUS or NO_MATCH rather than guessing."
)


class RealLLMProvider(ReasoningProvider):
    """Calls a real hosted LLM (Anthropic Messages API by default) with the
    bounded evidence M5 assembled, and validates the reply against
    :class:`AIDecision`. Never fabricates a response - a network/auth/
    parsing failure is raised, exactly like any other provider failure, and
    is handled the same way by ``M5ReasoningEngine`` (safe ESCALATE)."""

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_ANTHROPIC_MODEL,
        base_url: str = _DEFAULT_ANTHROPIC_URL,
        timeout_seconds: float = 30.0,
    ):
        if not api_key:
            raise ValueError("RealLLMProvider requires a non-empty api_key")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def reason(self, case_evidence: dict) -> AIDecision:
        body = json.dumps({
            "model": self.model,
            "max_tokens": 512,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": json.dumps(case_evidence, default=str)},
            ],
        }).encode("utf-8")

        request = urllib.request.Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            # Network/auth/timeout failure - re-raised as-is, caught and
            # audited by M5ReasoningEngine as PROVIDER_FAILED. Never
            # swallowed into a fabricated "successful" decision.
            raise ConnectionError(f"RealLLMProvider request failed: {e}") from e

        text_blocks = [b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"]
        payload_text = "".join(text_blocks).strip()
        payload_text = _strip_code_fences(payload_text)

        parsed = json.loads(payload_text)  # raises json.JSONDecodeError -> ValueError subclass on malformed output
        return AIDecision(**parsed)  # raises pydantic.ValidationError on schema violation


def _strip_code_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ---------------------------------------------------------------------------
# Test-only providers
# ---------------------------------------------------------------------------

class MockProvider(ReasoningProvider):
    """Deterministic, reproducible stand-in for a real provider - for
    tests only, never used to score DEV/HOLDOUT. Requires an explicit
    ``mock_response`` for a successful call; unlike the M8 bug, there is
    no silent default that produces a broken call - omitting
    ``mock_response`` and calling ``reason()`` raises immediately and
    obviously (see ``test_mock_provider_requires_explicit_response``)."""

    def __init__(self, mock_response: Optional[dict] = None, should_fail: bool = False):
        self.mock_response = mock_response
        self.should_fail = should_fail

    def reason(self, case_evidence: dict) -> AIDecision:
        if self.should_fail:
            raise ConnectionError("Mock network failure")
        if self.mock_response is None:
            raise ValueError(
                "MockProvider.reason() called with no mock_response configured. "
                "This is a test-harness error, not a provider failure - supply an "
                "explicit response, or use should_fail=True / FailingProvider to "
                "test failure handling on purpose."
            )
        return AIDecision(**self.mock_response)


class FailingProvider(ReasoningProvider):
    """Explicit, self-documenting provider for failure-path tests (timeouts,
    outages, credential errors). Equivalent to ``MockProvider(should_fail=
    True)`` but named for exactly what it is, per the "RealLLMProvider /
    MockProvider / FailingProvider" shape called out in the M9 brief."""

    def __init__(self, exception: Optional[BaseException] = None):
        self.exception = exception or ConnectionError("Simulated provider failure")

    def reason(self, case_evidence: dict) -> AIDecision:
        raise self.exception


# ---------------------------------------------------------------------------
# Provider factory - dependency injection entry point
# ---------------------------------------------------------------------------

def build_provider() -> Optional[ReasoningProvider]:
    """The single place a pipeline run decides which provider M5 gets.

    Reads three environment variables:

        AI_PROVIDER   e.g. "anthropic". If unset/empty, no real provider is
                      configured and this returns ``None``.
        AI_API_KEY    required if AI_PROVIDER is set; if missing, returns
                      ``None`` rather than raising, so a pipeline run
                      without credentials degrades to "M5 unavailable"
                      instead of crashing.
        AI_MODEL      optional, defaults to a fixed model string per
                      provider.

    Returns ``None`` when no usable provider is configured - callers
    (scripts/run_m6.py) must treat that exactly like "M5 unavailable" and
    skip AI reasoning, never falling back to a mock. This is the fix for
    the M8 defect: the old code path always got *some* provider object
    (a broken one); this factory can genuinely return nothing, and does,
    in this sandbox (no AI_API_KEY is configured here - see
    M9_CHANGELOG.md for confirmation this was checked).
    """
    provider_name = os.environ.get("AI_PROVIDER", "").strip().lower()
    if not provider_name:
        return None

    api_key = os.environ.get("AI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.environ.get("AI_MODEL", "").strip() or _DEFAULT_ANTHROPIC_MODEL

    if provider_name == "anthropic":
        return RealLLMProvider(api_key=api_key, model=model)

    # Unknown provider name configured: fail safe (no provider) rather
    # than guessing which backend was meant.
    return None

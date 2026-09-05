"""
M5 provider abstraction.

Production:
    RealLLMProvider -> Google Gemini API

Testing:
    MockProvider
    FailingProvider

M5 never has access to ground truth.
M6 remains the final financial-policy authority.
"""

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional

from src.m5_schema import AIDecision


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class ReasoningProvider(ABC):
    """Interface used by M5 for bounded AI reasoning."""

    @abstractmethod
    def reason(self, case_evidence: dict) -> AIDecision:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Gemini configuration
# ---------------------------------------------------------------------------

_DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"

_DEFAULT_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
)

_SYSTEM_PROMPT = """
You are a bounded financial reconciliation reasoning assistant.

You are given ONE payment that a deterministic reconciliation engine
could not confidently resolve, together with candidate settlements that
the engine already generated.

You MUST reason only from the supplied evidence.

You do NOT have access to ground truth.
You MUST NOT invent missing evidence.
You MUST NOT invent candidate IDs.

Your job is to recommend one of:

MATCH
NO_MATCH
AMBIGUOUS

Rules:

1. MATCH is allowed only when one supplied candidate is clearly supported
   by the available evidence.

2. selected_candidate_id must be exactly one of the supplied candidate IDs
   when decision is MATCH.

3. For NO_MATCH or AMBIGUOUS, selected_candidate_id must be null.

4. If the evidence is insufficient or two candidates are similarly plausible,
   choose AMBIGUOUS rather than guessing.

5. Confidence must represent confidence in the recommendation, not certainty
   about hidden ground truth.

6. recommended_action must be one of:
   ACCEPT
   ESCALATE
   REQUEST_MORE_DATA

Return ONLY JSON matching the supplied response schema.
"""


# ---------------------------------------------------------------------------
# Production provider
# ---------------------------------------------------------------------------

class RealLLMProvider(ReasoningProvider):
    """
    Production Gemini provider.

    The API key is read from the backend environment only.
    No API key is ever exposed to the React frontend.

    Gemini is asked for structured JSON and the response is validated
    through AIDecision before M5 can use it.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_GEMINI_MODEL,
        timeout_seconds: float = 30.0,
    ):
        if not api_key:
            raise ValueError("RealLLMProvider requires a non-empty api_key")

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def reason(self, case_evidence: dict) -> AIDecision:
        url = f"{_DEFAULT_GEMINI_URL}{self.model}:generateContent"

        response_schema = {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["MATCH", "NO_MATCH", "AMBIGUOUS"],
                },
                "selected_candidate_id": {
                    "type": "string",
                    "nullable": True,
                },
                "confidence": {
                    "type": "number",
                },
                "reasoning": {
                    "type": "string",
                },
                "missing_evidence": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "recommended_action": {
                    "type": "string",
                    "enum": [
                        "ACCEPT",
                        "ESCALATE",
                        "REQUEST_MORE_DATA",
                    ],
                },
            },
            "required": [
                "decision",
                "selected_candidate_id",
                "confidence",
                "reasoning",
                "missing_evidence",
                "recommended_action",
            ],
        }

        request_body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": _SYSTEM_PROMPT,
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                case_evidence,
                                default=str,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }

        body = json.dumps(request_body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw_response = json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""

            raise ConnectionError(
                f"Gemini API HTTP {exc.code}: {error_body[:500]}"
            ) from exc

        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Gemini API request failed: {exc}"
            ) from exc

        except TimeoutError as exc:
            raise ConnectionError(
                "Gemini API request timed out"
            ) from exc

        # Gemini returns:
        #
        # candidates[0]
        #   -> content
        #       -> parts
        #           -> text
        #
        candidates = raw_response.get("candidates", [])

        if not candidates:
            raise ValueError(
                "Gemini returned no candidates"
            )

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        text_parts = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict)
            and part.get("text")
        ]

        payload_text = "".join(text_parts).strip()

        if not payload_text:
            raise ValueError(
                "Gemini returned an empty response"
            )

        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemini returned malformed JSON: {payload_text[:500]}"
            ) from exc

        # Final schema validation.
        return AIDecision(**parsed)


# ---------------------------------------------------------------------------
# Test-only providers
# ---------------------------------------------------------------------------

class MockProvider(ReasoningProvider):
    """
    Deterministic provider for tests only.

    Requires an explicit response. It never generates fake AI output.
    """

    def __init__(
        self,
        mock_response: Optional[dict] = None,
        should_fail: bool = False,
    ):
        self.mock_response = mock_response
        self.should_fail = should_fail

    def reason(self, case_evidence: dict) -> AIDecision:
        if self.should_fail:
            raise ConnectionError("Mock network failure")

        if self.mock_response is None:
            raise ValueError(
                "MockProvider.reason() called with no mock_response configured."
            )

        return AIDecision(**self.mock_response)


class FailingProvider(ReasoningProvider):
    """Explicit provider used to test failure handling."""

    def __init__(
        self,
        exception: Optional[BaseException] = None,
    ):
        self.exception = exception or ConnectionError(
            "Simulated provider failure"
        )

    def reason(self, case_evidence: dict) -> AIDecision:
        raise self.exception


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def build_provider() -> Optional[ReasoningProvider]:
    """
    Build the real M5 provider from backend environment variables.

    Supported configuration:

        AI_PROVIDER=gemini
        AI_API_KEY=<Gemini API key>
        AI_MODEL=gemini-3.6-flash

    GEMINI_API_KEY is also accepted as a fallback.

    If credentials are missing, return None so the pipeline safely
    operates with M5 unavailable instead of fabricating AI output.
    """

    provider_name = os.environ.get(
        "AI_PROVIDER",
        "",
    ).strip().lower()

    if not provider_name:
        return None

    api_key = os.environ.get(
        "AI_API_KEY",
        "",
    ).strip()

    # Also support Google's conventional environment variable.
    if not api_key:
        api_key = os.environ.get(
            "GEMINI_API_KEY",
            "",
        ).strip()

    if not api_key:
        return None

    model = os.environ.get(
        "AI_MODEL",
        "",
    ).strip() or _DEFAULT_GEMINI_MODEL

    if provider_name == "gemini":
        return RealLLMProvider(
            api_key=api_key,
            model=model,
        )

    return None

"""
Provider-level tests for the M9 fix (src/m5_provider.py).

These tests are deliberately independent of M5ReasoningEngine/M6.
They test the provider abstraction itself:
- dependency injection
- MockProvider safety
- FailingProvider behavior
- Gemini RealLLMProvider response parsing
- schema validation
- network failure handling

No real Gemini API call is made by these tests.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from src.m5_provider import (
    ReasoningProvider,
    RealLLMProvider,
    MockProvider,
    FailingProvider,
    build_provider,
)

from src.m5_schema import AIDecision


# ---------------------------------------------------------------------------
# ReasoningProvider is a real abstract interface
# ---------------------------------------------------------------------------

def test_reasoning_provider_is_abstract():
    with pytest.raises(TypeError):
        ReasoningProvider()


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------

def test_mock_provider_requires_explicit_response():
    """
    The M8 defect: MockProvider() with no mock_response silently produced
    a TypeError deep inside AIDecision(**None).

    M9 behavior:
    calling reason() with no configured response raises a clear ValueError.
    """
    provider = MockProvider()

    with pytest.raises(ValueError, match="no mock_response configured"):
        provider.reason({"payment_id": "PAY_1"})


def test_mock_provider_returns_validated_match():
    provider = MockProvider({
        "decision": "MATCH",
        "selected_candidate_id": "STL_1",
        "confidence": 0.95,
        "reasoning": "clear id match",
        "missing_evidence": [],
        "recommended_action": "ACCEPT",
    })

    decision = provider.reason({"payment_id": "PAY_1"})

    assert isinstance(decision, AIDecision)
    assert decision.decision == "MATCH"
    assert decision.selected_candidate_id == "STL_1"


def test_mock_provider_rejects_malformed_response_via_schema():
    """
    MockProvider does not bypass AIDecision validation.
    """
    provider = MockProvider({
        "decision": "MATCH",
        "selected_candidate_id": None,
        "confidence": 0.95,
        "reasoning": "bad",
        "missing_evidence": [],
        "recommended_action": "ACCEPT",
    })

    with pytest.raises(ValidationError):
        provider.reason({})


def test_mock_provider_should_fail_flag():
    provider = MockProvider(should_fail=True)

    with pytest.raises(ConnectionError):
        provider.reason({})


# ---------------------------------------------------------------------------
# FailingProvider
# ---------------------------------------------------------------------------

def test_failing_provider_default_exception():
    provider = FailingProvider()

    with pytest.raises(ConnectionError):
        provider.reason({})


def test_failing_provider_custom_exception():
    provider = FailingProvider(
        exception=TimeoutError("simulated timeout")
    )

    with pytest.raises(TimeoutError):
        provider.reason({})


# ---------------------------------------------------------------------------
# build_provider - dependency injection factory
# ---------------------------------------------------------------------------

def test_build_provider_returns_none_with_no_env(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert build_provider() is None


def test_build_provider_returns_none_when_provider_set_but_no_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert build_provider() is None


def test_build_provider_returns_none_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "some_unsupported_backend")
    monkeypatch.setenv("AI_API_KEY", "fake-key")

    assert build_provider() is None


def test_build_provider_returns_real_provider_when_fully_configured(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("AI_MODEL", "gemini-3.6-flash")

    provider = build_provider()

    assert isinstance(provider, RealLLMProvider)
    assert provider.model == "gemini-3.6-flash"


# ---------------------------------------------------------------------------
# Helper for mocking Gemini API responses
# ---------------------------------------------------------------------------

def _fake_http_response(payload_dict):
    """
    Build a response using Gemini's generateContent response structure.
    """

    body = json.dumps({
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps(payload_dict)
                }]
            }
        }]
    }).encode()

    cm = MagicMock()

    cm.__enter__.return_value.read.return_value = body

    return cm


# ---------------------------------------------------------------------------
# RealLLMProvider
# ---------------------------------------------------------------------------

def test_real_llm_provider_requires_api_key():
    with pytest.raises(ValueError):
        RealLLMProvider(api_key="")


def test_real_llm_provider_parses_valid_response():
    provider = RealLLMProvider(api_key="fake-key")

    good_payload = {
        "decision": "AMBIGUOUS",
        "selected_candidate_id": None,
        "confidence": 0.5,
        "reasoning": "two equally plausible candidates",
        "missing_evidence": [
            "no reference id on either candidate"
        ],
        "recommended_action": "ESCALATE",
    }

    with patch(
        "src.m5_provider.urllib.request.urlopen",
        return_value=_fake_http_response(good_payload),
    ):
        decision = provider.reason({
            "payment_id": "PAY_1",
            "candidate_ids": ["A", "B"],
        })

    assert decision.decision == "AMBIGUOUS"
    assert decision.selected_candidate_id is None


def test_real_llm_provider_strips_markdown_code_fences():
    provider = RealLLMProvider(api_key="fake-key")

    payload = {
        "decision": "NO_MATCH",
        "selected_candidate_id": None,
        "confidence": 0.6,
        "reasoning": "no candidate is plausible",
        "missing_evidence": [],
        "recommended_action": "ESCALATE",
    }

    fenced_text = "```json\n" + json.dumps(payload) + "\n```"

    body = json.dumps({
        "candidates": [{
            "content": {
                "parts": [{
                    "text": fenced_text
                }]
            }
        }]
    }).encode()

    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body

    with patch(
        "src.m5_provider.urllib.request.urlopen",
        return_value=cm,
    ):
        decision = provider.reason({
            "payment_id": "PAY_1"
        })

    assert decision.decision == "NO_MATCH"


def test_real_llm_provider_malformed_json_raises():
    provider = RealLLMProvider(api_key="fake-key")

    body = json.dumps({
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "not json at all"
                }]
            }
        }]
    }).encode()

    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body

    with patch(
        "src.m5_provider.urllib.request.urlopen",
        return_value=cm,
    ):
        with pytest.raises(Exception):
            provider.reason({
                "payment_id": "PAY_1"
            })


def test_real_llm_provider_network_failure_raises_connectionerror():
    import urllib.error

    provider = RealLLMProvider(api_key="fake-key")

    with patch(
        "src.m5_provider.urllib.request.urlopen",
        side_effect=urllib.error.URLError("no route to host"),
    ):
        with pytest.raises(ConnectionError):
            provider.reason({
                "payment_id": "PAY_1"
            })


def test_real_llm_provider_hallucinated_schema_field_rejected():
    """
    Model returns a decision outside the allowed Literal.
    It must raise ValidationError and never be silently coerced.
    """

    provider = RealLLMProvider(api_key="fake-key")

    bad_payload = {
        "decision": "PROBABLY_MATCH",
        "selected_candidate_id": "STL_1",
        "confidence": 0.9,
        "reasoning": "x",
        "missing_evidence": [],
        "recommended_action": "ACCEPT",
    }

    with patch(
        "src.m5_provider.urllib.request.urlopen",
        return_value=_fake_http_response(bad_payload),
    ):
        with pytest.raises(ValidationError):
            provider.reason({
                "payment_id": "PAY_1"
            })

from types import SimpleNamespace

import groq
import httpx
import pytest

import services.llm as llm
from services.llm import (
    APIError,
    AuthenticationError,
    RateLimitError,
    TokenLimitError,
    analyze_resumes,
    build_prompt,
)


def _chat_response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _groq_error(cls, status_code, message="boom"):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return cls(message, response=response, body=None)


# --- build_prompt -----------------------------------------------------------


def test_build_prompt_includes_all_sections():
    out = build_prompt("TEMPLATE", "requisitos da vaga", {"a.md": "CV Alice", "b.md": "CV Bob"})
    assert out.startswith("TEMPLATE")
    assert "**REQUISITOS DA VAGA:**" in out
    assert "requisitos da vaga" in out
    assert "**CURRÍCULOS DOS CANDIDATOS:**" in out
    assert "CV Alice" in out
    assert "CV Bob" in out


def test_build_prompt_joins_resumes_as_bullets():
    out = build_prompt("T", "R", {"a": "X", "b": "Y"})
    assert "- X" in out
    assert "- Y" in out


def test_build_prompt_single_resume():
    out = build_prompt("T", "R", {"only.md": "conteudo"})
    assert "- conteudo" in out


def test_build_prompt_raises_token_limit_error_when_too_large():
    huge_resume = "x" * (llm._MAX_PROMPT_TOKENS * llm._CHARS_PER_TOKEN)
    with pytest.raises(TokenLimitError):
        build_prompt("T", "R", {"a.md": huge_resume})


def test_estimate_tokens():
    assert llm.estimate_tokens("abcd") == 1
    assert llm.estimate_tokens("abcdefgh") == 2


# --- analyze_resumes success ------------------------------------------------


def test_analyze_resumes_returns_content(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return _chat_response("RESULTADO DA ANALISE")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.chat = FakeChat()

    monkeypatch.setattr(llm, "Groq", FakeClient)
    result = analyze_resumes(api_key="key", model="the-model", prompt="the-prompt")

    assert result == "RESULTADO DA ANALISE"
    assert captured["api_key"] == "key"
    assert captured["kwargs"]["model"] == "the-model"
    assert captured["kwargs"]["messages"][-1]["content"] == "the-prompt"


# --- analyze_resumes error mapping ------------------------------------------


def _client_raising(error):
    class FakeCompletions:
        def create(self, **kwargs):
            raise error

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key=None):
            self.chat = FakeChat()

    return FakeClient


@pytest.mark.parametrize(
    "make_error,expected",
    [
        (lambda: _groq_error(groq.AuthenticationError, 401), AuthenticationError),
        (lambda: _groq_error(groq.PermissionDeniedError, 403), AuthenticationError),
        (lambda: _groq_error(groq.RateLimitError, 429), RateLimitError),
        (lambda: _groq_error(groq.APIStatusError, 413, "payload too large"), TokenLimitError),
    ],
)
def test_analyze_resumes_maps_status_codes(monkeypatch, make_error, expected):
    monkeypatch.setattr(llm, "Groq", _client_raising(make_error()))
    with pytest.raises(expected):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_token_limit_by_message(monkeypatch):
    error = _groq_error(groq.BadRequestError, 400, "Request is too large")
    monkeypatch.setattr(llm, "Groq", _client_raising(error))
    with pytest.raises(TokenLimitError):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_token_limit_by_token_and_limit(monkeypatch):
    error = _groq_error(groq.BadRequestError, 400, "token limit exceeded")
    monkeypatch.setattr(llm, "Groq", _client_raising(error))
    with pytest.raises(TokenLimitError):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_generic_error_becomes_apierror(monkeypatch):
    error = _groq_error(groq.InternalServerError, 500, "server exploded")
    monkeypatch.setattr(llm, "Groq", _client_raising(error))
    with pytest.raises(APIError) as excinfo:
        analyze_resumes("k", "m", "p")
    assert "server exploded" in excinfo.value.message


def test_analyze_resumes_connection_error_becomes_apierror(monkeypatch):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    error = groq.APIConnectionError(message="connection failed", request=request)
    monkeypatch.setattr(llm, "Groq", _client_raising(error))
    with pytest.raises(APIError) as excinfo:
        analyze_resumes("k", "m", "p")
    assert "connection failed" in excinfo.value.message

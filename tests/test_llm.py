from types import SimpleNamespace

import pytest
from huggingface_hub.errors import HfHubHTTPError

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


def _hf_error(status_code, message="boom"):
    response = SimpleNamespace(
        status_code=status_code,
        headers={},
        request=SimpleNamespace(method="POST", url="http://x"),
    )
    return HfHubHTTPError(message, response=response)


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

    class FakeClient:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key

        def chat_completion(self, **kwargs):
            captured["kwargs"] = kwargs
            return _chat_response("RESULTADO DA ANALISE")

    monkeypatch.setattr(llm, "InferenceClient", FakeClient)
    result = analyze_resumes(api_key="key", model="the-model", prompt="the-prompt")

    assert result == "RESULTADO DA ANALISE"
    assert captured["api_key"] == "key"
    assert captured["kwargs"]["model"] == "the-model"
    assert captured["kwargs"]["messages"][-1]["content"] == "the-prompt"


# --- analyze_resumes error mapping ------------------------------------------


def _client_raising(error):
    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def chat_completion(self, **kwargs):
            raise error

    return FakeClient


@pytest.mark.parametrize(
    "status_code,expected",
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (413, TokenLimitError),
    ],
)
def test_analyze_resumes_maps_status_codes(monkeypatch, status_code, expected):
    monkeypatch.setattr(llm, "InferenceClient", _client_raising(_hf_error(status_code)))
    with pytest.raises(expected):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_token_limit_by_message(monkeypatch):
    monkeypatch.setattr(
        llm, "InferenceClient", _client_raising(_hf_error(400, "Request is too large"))
    )
    with pytest.raises(TokenLimitError):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_token_limit_by_token_and_limit(monkeypatch):
    monkeypatch.setattr(
        llm, "InferenceClient", _client_raising(_hf_error(400, "token limit exceeded"))
    )
    with pytest.raises(TokenLimitError):
        analyze_resumes("k", "m", "p")


def test_analyze_resumes_generic_error_becomes_apierror(monkeypatch):
    monkeypatch.setattr(
        llm, "InferenceClient", _client_raising(_hf_error(500, "server exploded"))
    )
    with pytest.raises(APIError) as excinfo:
        analyze_resumes("k", "m", "p")
    assert "server exploded" in excinfo.value.message

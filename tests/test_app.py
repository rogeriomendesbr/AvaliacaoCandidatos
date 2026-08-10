from pathlib import Path

import pytest

import services.config as config
import services.extract as extract
import services.llm as llm

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


def _app_test():
    testing = pytest.importorskip("streamlit.testing.v1")
    # default_timeout maior que o padrão (3s): interações com widgets como
    # st.pills podem levar mais tempo que isso em execuções mais pesadas.
    return testing.AppTest.from_file(APP_PATH, default_timeout=15)


def _ready_app(monkeypatch, api_key="fake-token"):
    """App com um currículo carregado e requisitos preenchidos, pronto para clicar em Avaliar."""
    monkeypatch.setenv("GROQ_API_KEY", api_key)
    at = _app_test()
    at.session_state["uploaded_files"] = {"cv.md": "Experiência em Python e Streamlit"}
    at.run()
    at.text_area[0].set_value("Requisitos da vaga")
    return at


def test_app_runs_without_exception():
    at = _app_test().run()
    assert not at.exception


def test_app_shows_title():
    at = _app_test().run()
    assert any("Avaliação de Candidatos" in s.value for s in at.subheader)


def test_app_starts_with_no_resumes_loaded():
    at = _app_test().run()
    assert at.session_state["uploaded_files"] == {}


def test_app_validates_missing_inputs():
    at = _app_test().run()
    at.button(key="go-button").click().run()
    assert any("Por favor" in e.value for e in at.error)


# --- upload de currículos -----------------------------------------------


def test_upload_markdown_file_adds_to_session_state():
    at = _app_test().run()
    at.file_uploader[0].set_value(("cv.md", "Nome: Ana Souza".encode("utf-8"), "text/markdown"))
    at.run()

    assert not at.exception
    assert at.session_state["uploaded_files"] == {"cv.md": "Nome: Ana Souza"}
    assert at.session_state["uploader_key"] == 1


def test_upload_ocr_error_shows_message_and_discards_file(monkeypatch):
    def raise_ocr_error(name, data):
        raise extract.OCRError("Tesseract não encontrado")

    monkeypatch.setattr(extract, "extract_resume", raise_ocr_error)

    at = _app_test().run()
    at.file_uploader[0].set_value(("scan.pdf", b"fake bytes", "application/pdf"))
    at.run()

    assert not at.exception
    assert any("Tesseract não encontrado" in e.value for e in at.error)
    assert at.session_state["uploaded_files"] == {}


def test_upload_doc_file_shows_friendly_error_without_crashing():
    """Regressão: um upload .doc já derrubou o app com uma exceção não
    capturável (Streamlit valida `type=[...]` antes do nosso código rodar).
    A extensão não é mais restringida no widget; extract_resume() agora
    rejeita com um erro amigável e o app segue funcionando normalmente."""
    at = _app_test().run()
    at.file_uploader[0].set_value(("cv.doc", b"\xd0\xcf\x11\xe0binario", "application/msword"))
    at.run()

    assert not at.exception
    assert any(".docx" in e.value for e in at.error)
    assert at.session_state["uploaded_files"] == {}


def test_upload_unexpected_error_shows_generic_message(monkeypatch):
    def raise_unexpected(name, data):
        raise RuntimeError("boom")

    monkeypatch.setattr(extract, "extract_resume", raise_unexpected)

    at = _app_test().run()
    at.file_uploader[0].set_value(("cv.pdf", b"fake bytes", "application/pdf"))
    at.run()

    assert not at.exception
    assert any("Não foi possível processar o arquivo" in e.value for e in at.error)
    assert at.session_state["uploaded_files"] == {}


def test_remove_uploaded_resume_via_pills():
    at = _app_test()
    at.session_state["uploaded_files"] = {"a.md": "conteúdo a", "b.md": "conteúdo b"}
    at.run()

    at.pills[0].set_value(["a.md"])
    at.run()

    assert not at.exception
    assert at.session_state["uploaded_files"] == {"b.md": "conteúdo b"}


# --- botão "Avaliar candidatos" -----------------------------------------


def test_analyze_missing_api_key_shows_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})

    at = _app_test()
    at.session_state["uploaded_files"] = {"cv.md": "conteúdo"}
    at.run()
    at.text_area[0].set_value("Requisitos")
    at.button(key="go-button").click().run()

    assert not at.exception
    assert any("API key da Groq" in e.value for e in at.error)


def test_analyze_prompt_too_large_shows_error_without_calling_api(monkeypatch):
    called = {"invoked": False}

    def spy(**kwargs):
        called["invoked"] = True
        return "não deveria ser chamado"

    monkeypatch.setattr(llm, "analyze_resumes", spy)
    monkeypatch.setenv("GROQ_API_KEY", "fake-token")

    at = _app_test()
    at.session_state["uploaded_files"] = {"cv.md": "x" * 500_000}
    at.run()
    at.text_area[0].set_value("Requisitos")
    at.button(key="go-button").click().run()

    assert not at.exception
    assert any("limite de tokens" in e.value for e in at.error)
    assert called["invoked"] is False


def test_analyze_success_shows_result_and_prompt_expander(monkeypatch):
    monkeypatch.setattr(llm, "analyze_resumes", lambda **kwargs: "RESULTADO DA AVALIAÇÃO")
    at = _ready_app(monkeypatch)

    at.button(key="go-button").click().run()

    assert not at.exception
    assert any("sucesso" in s.value for s in at.success)
    assert any("RESULTADO DA AVALIAÇÃO" in m.value for m in at.markdown)
    assert at.expander[0].label == "Prompt enviado ao modelo"


@pytest.mark.parametrize(
    "error,expected_snippet",
    [
        (llm.RateLimitError(), "Limite de uso atingido no Groq.com"),
        (llm.AuthenticationError(), "autenticação"),
        (llm.APIError("mensagem específica da API"), "mensagem específica da API"),
        (llm.TokenLimitError(), "limite de tokens"),
        (RuntimeError("erro totalmente inesperado"), "Anomalia inesperada"),
    ],
)
def test_analyze_maps_errors_to_messages(monkeypatch, error, expected_snippet):
    def raiser(**kwargs):
        raise error

    monkeypatch.setattr(llm, "analyze_resumes", raiser)
    at = _ready_app(monkeypatch)

    at.button(key="go-button").click().run()

    assert not at.exception
    assert any(expected_snippet in e.value for e in at.error)


# --- botão "Limpar dados" -------------------------------------------------


def test_clear_button_resets_all_state(monkeypatch):
    monkeypatch.setattr(llm, "analyze_resumes", lambda **kwargs: "RESULTADO DA AVALIAÇÃO")
    at = _ready_app(monkeypatch)
    at.button(key="go-button").click().run()
    assert any("sucesso" in s.value for s in at.success)  # sanity: avaliação rodou

    uploader_key_before = at.session_state["uploader_key"]
    requisites_key_before = at.session_state["requisites_key"]

    at.button(key="clear-button").click().run()

    assert not at.exception
    assert at.session_state["uploaded_files"] == {}
    assert at.session_state["analysis_message"] is None
    assert not at.text_area[0].value
    assert at.session_state["uploader_key"] > uploader_key_before
    assert at.session_state["requisites_key"] > requisites_key_before
    assert not at.success
    assert not at.expander

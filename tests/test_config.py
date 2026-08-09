import services.config as config


def test_get_secret_prefers_env_over_secrets(monkeypatch):
    monkeypatch.setenv("MY_VAR", "from-env")
    monkeypatch.setattr(config.st, "secrets", {"sec": {"key": "from-secrets"}})
    assert config.get_secret("MY_VAR", "sec", "key") == "from-env"


def test_get_secret_falls_back_to_secrets(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)
    monkeypatch.setattr(config.st, "secrets", {"sec": {"key": "from-secrets"}})
    assert config.get_secret("MY_VAR", "sec", "key") == "from-secrets"


def test_get_secret_returns_default_when_section_missing(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_secret("MY_VAR", "sec", "key", default="fallback") == "fallback"


def test_get_secret_returns_default_when_key_missing(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)
    monkeypatch.setattr(config.st, "secrets", {"sec": {}})
    assert config.get_secret("MY_VAR", "sec", "key", default="fallback") == "fallback"


def test_get_secret_handles_missing_secrets_file(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)

    class NoSecretsFile:
        def __getitem__(self, key):
            raise FileNotFoundError

    monkeypatch.setattr(config.st, "secrets", NoSecretsFile())
    assert config.get_secret("MY_VAR", "sec", "key", default="d") == "d"


def test_get_secret_returns_default_when_secrets_value_empty(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)
    monkeypatch.setattr(config.st, "secrets", {"sec": {"key": ""}})
    assert config.get_secret("MY_VAR", "sec", "key", default="fallback") == "fallback"


def test_get_secret_returns_default_when_env_empty(monkeypatch):
    monkeypatch.setenv("MY_VAR", "")
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_secret("MY_VAR", "sec", "key", default="fallback") == "fallback"


def test_get_secret_empty_secrets_value_falls_back_to_default_model(monkeypatch):
    monkeypatch.delenv("HF_MODEL", raising=False)
    monkeypatch.setattr(config.st, "secrets", {"huggingface": {"model": ""}})
    assert config.get_hf_model() == "meta-llama/Llama-3.3-70B-Instruct"


def test_get_secret_empty_default(monkeypatch):
    monkeypatch.delenv("MY_VAR", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_secret("MY_VAR", "sec", "key") == ""


def test_get_hf_api_key_from_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_abc")
    assert config.get_hf_api_key() == "hf_abc"


def test_get_hf_model_default(monkeypatch):
    monkeypatch.delenv("HF_MODEL", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_hf_model() == "meta-llama/Llama-3.3-70B-Instruct"


def test_get_hf_model_from_env(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    assert config.get_hf_model() == "meta-llama/Llama-3.1-8B-Instruct"


def test_get_ocr_lang_default(monkeypatch):
    monkeypatch.delenv("OCR_LANG", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_ocr_lang() == "por"


def test_get_ocr_lang_from_env(monkeypatch):
    monkeypatch.setenv("OCR_LANG", "eng")
    assert config.get_ocr_lang() == "eng"


def test_get_tesseract_cmd_default_empty(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(config.st, "secrets", {})
    assert config.get_tesseract_cmd() == ""


def test_get_tesseract_cmd_from_env(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", "/usr/bin/tesseract")
    assert config.get_tesseract_cmd() == "/usr/bin/tesseract"

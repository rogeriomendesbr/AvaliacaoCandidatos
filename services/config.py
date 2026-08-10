import os
import streamlit as st


def get_secret(env_var: str, toml_section: str, toml_key: str, default: str = "") -> str:
    if value := os.environ.get(env_var):
        return value
    try:
        if value := st.secrets[toml_section][toml_key]:
            return value
    except (KeyError, FileNotFoundError):
        pass
    return default


def get_groq_api_key() -> str:
    return get_secret("GROQ_API_KEY", "groq", "api_key")


def get_groq_model() -> str:
    return get_secret("GROQ_MODEL", "groq", "model", default="openai/gpt-oss-20b")


def get_tesseract_cmd() -> str:
    return get_secret("TESSERACT_CMD", "ocr", "tesseract_cmd")


def get_ocr_lang() -> str:
    return get_secret("OCR_LANG", "ocr", "lang", default="por")

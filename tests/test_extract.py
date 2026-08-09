import io
import sys
import types
import zipfile

import pymupdf
import pytest

import services.extract as extract
from services.extract import (
    OCRError,
    UnsupportedFormatError,
    _is_text_based,
    _text_to_markdown,
    extract_resume,
)


# --- helpers ----------------------------------------------------------------


def _text_pdf_bytes(text="Experiencia profissional em Python e Streamlit no desenvolvimento web"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def _image_pdf_bytes():
    """PDF sem texto extraível — simula um currículo digitalizado (imagem)."""
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()


_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _docx_bytes(body_xml):
    """Monta um .docx mínimo porém válido a partir do XML do corpo do documento."""
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body_xml}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


def _para(text, style=None, bold=False):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p>{props}<w:r>{run_props}<w:t>{text}</w:t></w:r></w:p>"


def _install_fake_pytesseract(monkeypatch, ocr_text="TEXTO EXTRAIDO", raises=None):
    fake = types.ModuleType("pytesseract")

    class TesseractNotFoundError(Exception):
        pass

    class TesseractError(Exception):
        pass

    fake.TesseractNotFoundError = TesseractNotFoundError
    fake.TesseractError = TesseractError
    fake.pytesseract = types.SimpleNamespace(tesseract_cmd=None)
    calls = {}

    def image_to_string(image, lang=None):
        calls["lang"] = lang
        calls["called"] = calls.get("called", 0) + 1
        if raises is not None:
            raise raises
        return ocr_text

    fake.image_to_string = image_to_string
    fake.calls = calls
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    return fake


# --- _text_to_markdown ------------------------------------------------------


def test_text_to_markdown_collapses_blank_lines():
    assert _text_to_markdown("linha1\n\n\n\nlinha2") == "linha1\n\nlinha2"


def test_text_to_markdown_strips_trailing_whitespace():
    assert _text_to_markdown("linha1   \nlinha2\t") == "linha1\nlinha2"


def test_text_to_markdown_strips_edges():
    assert _text_to_markdown("\n\n  conteudo  \n\n") == "conteudo"


# --- _is_text_based ---------------------------------------------------------


def test_is_text_based_true_for_text_pdf():
    doc = pymupdf.open(stream=_text_pdf_bytes(), filetype="pdf")
    assert _is_text_based(doc) is True


def test_is_text_based_false_for_image_pdf():
    doc = pymupdf.open(stream=_image_pdf_bytes(), filetype="pdf")
    assert _is_text_based(doc) is False


# --- extract_resume: text sources -------------------------------------------


def test_extract_markdown_file_decodes_utf8():
    assert extract_resume("cv.md", "Nome: João Ção".encode("utf-8")) == "Nome: João Ção"


def test_extract_text_pdf_returns_markdown():
    out = extract_resume("cv.pdf", _text_pdf_bytes())
    assert "Python" in out


def test_extract_pdf_uppercase_extension():
    out = extract_resume("CV.PDF", _text_pdf_bytes())
    assert "Python" in out


# --- extract_resume: docx ---------------------------------------------------


def test_extract_docx_returns_text():
    out = extract_resume("cv.docx", _docx_bytes(_para("Desenvolvedor Python e Streamlit")))
    assert "Desenvolvedor Python e Streamlit" in out


def test_extract_docx_preserves_heading_as_atx():
    body = _para("Joao Silva", style="Heading1") + _para("Analista de dados")
    out = extract_resume("cv.docx", _docx_bytes(body))
    assert "# Joao Silva" in out
    assert "Analista de dados" in out


def test_extract_docx_preserves_bold_emphasis():
    out = extract_resume("cv.docx", _docx_bytes(_para("Experiencia", bold=True)))
    assert "**Experiencia**" in out


def test_extract_docx_preserves_accented_characters():
    out = extract_resume("cv.docx", _docx_bytes(_para("Formação: Ciência da Computação")))
    assert "Formação: Ciência da Computação" in out


def test_extract_docx_uppercase_extension():
    out = extract_resume("CV.DOCX", _docx_bytes(_para("Currículo em maiúsculas")))
    assert "Currículo em maiúsculas" in out


def test_extract_docx_output_is_normalized_markdown():
    body = "".join(_para(f"Linha {i}") for i in range(3))
    out = extract_resume("cv.docx", _docx_bytes(body))
    assert "\n\n\n" not in out
    assert out == out.strip()


def test_extract_legacy_doc_raises_unsupported_format():
    with pytest.raises(UnsupportedFormatError, match=".docx"):
        extract_resume("cv.doc", b"\xd0\xcf\x11\xe0qualquer binario OLE")


def test_extract_legacy_doc_uppercase_extension():
    with pytest.raises(UnsupportedFormatError):
        extract_resume("CV.DOC", b"\xd0\xcf\x11\xe0")


def test_extract_docx_not_mistaken_for_legacy_doc():
    out = extract_resume("cv.docx", _docx_bytes(_para("Nao deve virar erro")))
    assert "Nao deve virar erro" in out


# --- extract_resume: image sources (OCR) ------------------------------------


def test_image_pdf_routes_through_ocr(monkeypatch):
    fake = _install_fake_pytesseract(monkeypatch, ocr_text="Joao Silva\n\n\n\nDesenvolvedor")
    out = extract_resume("scan.pdf", _image_pdf_bytes())
    assert "Joao Silva" in out
    assert "Desenvolvedor" in out
    # resultado normalizado como markdown (sem linhas em branco excedentes)
    assert "\n\n\n" not in out
    assert fake.calls["called"] == 1


def test_ocr_uses_configured_language(monkeypatch):
    fake = _install_fake_pytesseract(monkeypatch)
    monkeypatch.setattr(extract, "get_ocr_lang", lambda: "eng")
    extract_resume("scan.pdf", _image_pdf_bytes())
    assert fake.calls["lang"] == "eng"


def test_ocr_applies_configured_tesseract_cmd(monkeypatch):
    fake = _install_fake_pytesseract(monkeypatch)
    monkeypatch.setattr(extract, "get_tesseract_cmd", lambda: "/custom/tesseract")
    extract_resume("scan.pdf", _image_pdf_bytes())
    assert fake.pytesseract.tesseract_cmd == "/custom/tesseract"


def test_ocr_raises_ocrerror_when_tesseract_not_found(monkeypatch):
    fake = _install_fake_pytesseract(monkeypatch)
    fake.image_to_string = lambda image, lang=None: (_ for _ in ()).throw(
        fake.TesseractNotFoundError()
    )
    with pytest.raises(OCRError):
        extract_resume("scan.pdf", _image_pdf_bytes())


def test_ocr_raises_ocrerror_on_tesseract_error(monkeypatch):
    fake = _install_fake_pytesseract(monkeypatch)
    fake.image_to_string = lambda image, lang=None: (_ for _ in ()).throw(
        fake.TesseractError("falhou")
    )
    with pytest.raises(OCRError):
        extract_resume("scan.pdf", _image_pdf_bytes())


def test_ocr_raises_ocrerror_when_library_missing(monkeypatch):
    # None em sys.modules faz `import pytesseract` levantar ImportError
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    with pytest.raises(OCRError):
        extract_resume("scan.pdf", _image_pdf_bytes())

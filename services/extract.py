import io
import re
from concurrent.futures import ThreadPoolExecutor

import mammoth
import pymupdf
import pymupdf4llm
from markdownify import markdownify

from services.config import get_ocr_lang, get_tesseract_cmd


class OCRError(Exception):
    pass


class UnsupportedFormatError(Exception):
    pass


# Mínimo de caracteres extraíveis para um PDF ser considerado baseado em texto.
_MIN_TEXT_CHARS = 32

# Resolução (DPI) usada para rasterizar as páginas antes do OCR.
_OCR_DPI = 300


def extract_resume(file_name: str, file_bytes: bytes) -> str:
    """Retorna o conteúdo do currículo em markdown, independentemente do formato de origem."""
    name = file_name.lower()
    if name.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if name.endswith(".docx"):
        return _extract_docx(file_bytes)
    if name.endswith(".doc"):
        raise UnsupportedFormatError(
            "O formato .doc (Word 97-2003) não é suportado. "
            "Envie o currículo em .txt, .md, .docx ou .pdf. No Word, use Salvar Como → .docx."
        )
    if name.endswith(".md") or name.endswith(".txt"):
        return file_bytes.decode("utf-8")
    raise UnsupportedFormatError(
        "Formato de arquivo não suportado. Envie o currículo em .txt, .md, .docx ou .pdf."
    )


def _extract_docx(file_bytes: bytes) -> str:
    """Converte um .docx em markdown via HTML, preservando a estrutura vinda dos estilos do Word."""
    result = mammoth.convert_to_html(io.BytesIO(file_bytes))
    return _text_to_markdown(markdownify(result.value, heading_style="ATX"))


def _extract_pdf(file_bytes: bytes) -> str:
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    if _is_text_based(doc):
        return pymupdf4llm.to_markdown(doc)
    return _ocr_pdf(doc)


def _is_text_based(doc) -> bool:
    """Considera o PDF baseado em texto se houver texto extraível suficiente."""
    total = 0
    for page in doc:
        total += len(page.get_text().strip())
        if total >= _MIN_TEXT_CHARS:
            return True
    return False


def _ocr_pdf(doc) -> str:
    """Lê um PDF baseado em imagem via OCR e devolve o texto em markdown."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise OCRError(
            "As bibliotecas de OCR (pytesseract e Pillow) não estão instaladas."
        ) from e

    if cmd := get_tesseract_cmd():
        pytesseract.pytesseract.tesseract_cmd = cmd

    lang = get_ocr_lang()
    # Rasterização via PyMuPDF é feita sequencialmente (não é thread-safe),
    # mas cada página é OCRizada em paralelo — o Tesseract roda como
    # subprocesso, então páginas independentes não competem pelo GIL.
    images = [
        Image.open(io.BytesIO(page.get_pixmap(dpi=_OCR_DPI).tobytes("png")))
        for page in doc
    ]
    try:
        with ThreadPoolExecutor(max_workers=min(len(images), 8) or 1) as executor:
            pages_text = list(
                executor.map(lambda img: pytesseract.image_to_string(img, lang=lang), images)
            )
    except pytesseract.TesseractNotFoundError as e:
        raise OCRError(
            "O executável do Tesseract OCR não foi encontrado. Instale o Tesseract "
            "e/ou defina a variável de ambiente TESSERACT_CMD com o caminho do executável."
        ) from e
    except pytesseract.TesseractError as e:
        raise OCRError(f"Falha ao executar o OCR: {e}") from e

    return _text_to_markdown("\n\n".join(pages_text))


def _text_to_markdown(text: str) -> str:
    """Normaliza o texto bruto do OCR em markdown (remove espaços à direita e linhas em branco excedentes)."""
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


__all__ = ["extract_resume", "OCRError", "UnsupportedFormatError"]

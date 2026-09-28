from pathlib import Path
import re

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


class ResumeParserError(ValueError):
    """Base error for resume text extraction failures."""


class UnsupportedResumeFormatError(ResumeParserError):
    pass


class EmptyDocumentError(ResumeParserError):
    pass


class CorruptedDocumentError(ResumeParserError):
    pass


def extract_text(file_path: str | Path, file_type: str) -> str:
    normalized_type = file_type.strip().lower().lstrip(".")
    if normalized_type in {"application/pdf"}:
        normalized_type = "pdf"
    elif normalized_type in {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        normalized_type = "docx"
    if normalized_type not in {"pdf", "docx"}:
        raise UnsupportedResumeFormatError("Resume parser supports only PDF and DOCX files.")

    path = Path(file_path)
    if not path.is_file():
        raise CorruptedDocumentError("The uploaded resume file could not be read.")

    try:
        raw_text = _extract_pdf(path) if normalized_type == "pdf" else _extract_docx(path)
    except ResumeParserError:
        raise
    except Exception as exc:
        raise CorruptedDocumentError(f"The {normalized_type.upper()} resume could not be read.") from exc

    text = normalize_whitespace(raw_text)
    if not text:
        raise EmptyDocumentError("The resume contains no extractable text.")
    return text


def normalize_whitespace(text: str) -> str:
    normalized_lines = []
    for source_line in text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").split("\n"):
        line = re.sub(r"[\t\v\u00a0 ]+", " ", source_line).strip()
        if line:
            normalized_lines.append(line)
        elif normalized_lines and normalized_lines[-1] != "":
            normalized_lines.append("")
    return "\n".join(normalized_lines).strip()


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path), strict=True)
    if reader.is_encrypted:
        raise CorruptedDocumentError("Password-protected PDF resumes are not supported.")
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(path: Path) -> str:
    document = Document(str(path))
    blocks = []
    for element in document.element.body.iterchildren():
        if isinstance(element, CT_P):
            blocks.append(Paragraph(element, document).text)
        elif isinstance(element, CT_Tbl):
            table = Table(element, document)
            for row in table.rows:
                cells = [cell.text for cell in row.cells]
                if any(cell.strip() for cell in cells):
                    blocks.append(" | ".join(cells))
    return "\n".join(blocks)
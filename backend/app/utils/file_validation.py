from io import BytesIO
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfReader


class UnsupportedResumeType(ValueError):
    pass


class InvalidResumeFile(ValueError):
    pass


MIME_TYPES = {
    ".pdf": ("pdf", "application/pdf"),
    ".docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
SAFE_STORED_FILENAME = re.compile(r"^[0-9a-f]{32}\.(pdf|docx)$")


def safe_original_filename(filename: str | None) -> str:
    normalized = (filename or "resume").replace("\\", "/")
    basename = PurePosixPath(normalized).name
    cleaned = "".join(character for character in basename if character.isprintable()).strip()
    return cleaned[:255] or "resume"


def validate_resume_file(
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> tuple[str, str, str]:
    original_filename = safe_original_filename(filename)
    extension = PurePosixPath(original_filename).suffix.lower()
    file_type_info = MIME_TYPES.get(extension)
    if file_type_info is None:
        raise UnsupportedResumeType("Unsupported file type. Upload a PDF or DOCX resume.")

    file_type, expected_mime = file_type_info
    supplied_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if supplied_mime not in {"", "application/octet-stream", expected_mime}:
        raise UnsupportedResumeType("The uploaded MIME type does not match the file extension.")
    if not data:
        raise InvalidResumeFile("The uploaded file is empty.")

    if file_type == "pdf":
        _validate_pdf(data)
    else:
        _validate_docx(data)
    return original_filename, file_type, expected_mime


def _validate_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise InvalidResumeFile("The file contents are not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) == 0:
            raise InvalidResumeFile("The PDF is encrypted or contains no pages.")
    except InvalidResumeFile:
        raise
    except Exception as exc:
        raise InvalidResumeFile("The PDF file is damaged or unreadable.") from exc


def _validate_docx(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 5000 or sum(member.file_size for member in members) > 50_000_000:
                raise InvalidResumeFile("The DOCX archive exceeds the processing limit.")
            required_files = {"[Content_Types].xml", "word/document.xml"}
            if not required_files.issubset(archive.namelist()):
                raise InvalidResumeFile("The DOCX file is missing required document content.")
            ElementTree.fromstring(archive.read("[Content_Types].xml"))
            ElementTree.fromstring(archive.read("word/document.xml"))
    except InvalidResumeFile:
        raise
    except Exception as exc:
        raise InvalidResumeFile("The DOCX file is damaged or unreadable.") from exc


def safe_stored_path(uploads_dir, stored_filename: str):
    if not SAFE_STORED_FILENAME.fullmatch(stored_filename):
        raise InvalidResumeFile("Stored resume filename is invalid.")
    root = uploads_dir.resolve()
    candidate = root / stored_filename
    if candidate.resolve(strict=False).parent != root:
        raise InvalidResumeFile("Stored resume path is outside the upload directory.")
    return candidate
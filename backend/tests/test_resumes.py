from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.agents.resume_analyzer import AIProviderError
from backend.app.database.base import Base
from backend.app.database.dependencies import get_db
from backend.app.main import app
from backend.app.models import Resume, ResumeAnalysisRecord
from backend.app.schemas.resume_analysis import ResumeAnalysis
import backend.app.services.resume_analysis_service as resume_analysis_service
from backend.tests.pdf_fixture import text_pdf_bytes


@pytest.fixture
def isolated_database(tmp_path):
    test_engine = create_engine(URL.create("sqlite", database=str(tmp_path / "resume-tests.db")))
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    yield session_factory
    test_engine.dispose()


@pytest.fixture
def client(isolated_database, tmp_path, monkeypatch):
    def override_get_db():
        with isolated_database() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def pdf_bytes() -> bytes:
    return text_pdf_bytes("Professional Experience")


def docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Resume fixture")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def authenticated_headers(client: TestClient) -> dict[str, str]:
    email = f"resume-{uuid4().hex}@example.org"
    password = "SecurePassphrase123"
    registration = client.post(
        "/api/auth/register",
        json={"name": "Resume Owner", "email": email, "password": password},
    )
    assert registration.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_upload_valid_pdf_with_safe_stored_filename(client, isolated_database):
    headers = authenticated_headers(client)
    response = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("../../resume.pdf", pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["original_filename"] == "resume.pdf"
    assert result["file_type"] == "pdf"
    assert result["file_size_bytes"] > 0
    assert "stored_filename" not in result

    with isolated_database() as db:
        resume = db.scalar(select(Resume).where(Resume.id == result["id"]))
        assert resume is not None
        assert resume.stored_filename != resume.original_filename
        assert "Professional Experience" in resume.extracted_text
        assert (settings.uploads_dir / resume.stored_filename).is_file()


def test_upload_valid_docx(client, isolated_database):
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={
            "file": (
                "resume.docx",
                docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    resume_id = response.json()["id"]
    assert response.json()["file_type"] == "docx"
    with isolated_database() as db:
        resume = db.scalar(select(Resume).where(Resume.id == resume_id))
        assert resume is not None
        assert "Resume fixture" in resume.extracted_text


def test_upload_rejects_invalid_extension(client):
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={"file": ("resume.txt", b"not a resume document", "text/plain")},
    )

    assert response.status_code == 415
    assert "PDF or DOCX" in response.json()["detail"]


def test_upload_rejects_mismatched_mime_type(client):
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={"file": ("resume.pdf", pdf_bytes(), "text/plain")},
    )

    assert response.status_code == 415
    assert "MIME type" in response.json()["detail"]


def test_upload_rejects_invalid_pdf_contents(client):
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={"file": ("resume.pdf", b"not really a pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert "valid PDF" in response.json()["detail"]


def test_upload_empty_document_is_not_persisted(client):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={"file": ("empty.pdf", output.getvalue(), "application/pdf")},
    )

    assert response.status_code == 422
    assert "no extractable text" in response.json()["detail"]
    assert list(settings.uploads_dir.iterdir()) == []


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 64)
    response = client.post(
        "/api/resumes/upload",
        headers=authenticated_headers(client),
        files={"file": ("resume.pdf", b"%PDF-" + b"x" * 100, "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 401
    assert client.get("/api/resumes").status_code == 401


def test_resume_list_and_detail_are_isolated_by_user(client):
    owner_headers = authenticated_headers(client)
    uploaded = client.post(
        "/api/resumes/upload",
        headers=owner_headers,
        files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")},
    )
    resume_id = uploaded.json()["id"]
    other_user_headers = authenticated_headers(client)

    assert [item["id"] for item in client.get("/api/resumes", headers=owner_headers).json()] == [resume_id]
    assert client.get("/api/resumes", headers=other_user_headers).json() == []
    assert client.get(f"/api/resumes/{resume_id}", headers=other_user_headers).status_code == 404
    assert client.delete(f"/api/resumes/{resume_id}", headers=other_user_headers).status_code == 404


def test_delete_removes_resume_record_and_file(client, isolated_database):
    headers = authenticated_headers(client)
    uploaded = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("resume.docx", docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    resume_id = uploaded.json()["id"]
    with isolated_database() as db:
        resume = db.scalar(select(Resume).where(Resume.id == resume_id))
        stored_path = settings.uploads_dir / resume.stored_filename
        assert stored_path.is_file()

    response = client.delete(f"/api/resumes/{resume_id}", headers=headers)

    assert response.status_code == 204
    assert client.get(f"/api/resumes/{resume_id}", headers=headers).status_code == 404
    assert not stored_path.exists()


def test_analyze_endpoint_persists_validated_result(client, isolated_database, monkeypatch):
    headers = authenticated_headers(client)
    uploaded = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")},
    )
    resume_id = uploaded.json()["id"]

    class FakeAnalyzer:
        model = "test-analyzer"

        async def analyze(self, resume_text):
            assert "Professional Experience" in resume_text
            return ResumeAnalysis(summary="Backend engineer.", technical_skills=["Python"])

    monkeypatch.setattr(resume_analysis_service, "ResumeAnalyzerAgent", FakeAnalyzer)
    response = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["result"]["summary"] == "Backend engineer."
    assert body["result"]["technical_skills"] == ["Python"]
    assert body["result"]["education"] == []
    with isolated_database() as db:
        record = db.scalar(select(ResumeAnalysisRecord).where(ResumeAnalysisRecord.id == body["id"]))
        assert record is not None
        assert record.resume_id == resume_id
        assert record.result_json["technical_skills"] == ["Python"]
        assert record.model_name == "test-analyzer"


def test_analyze_endpoint_does_not_call_agent_for_another_users_resume(client, monkeypatch):
    owner_headers = authenticated_headers(client)
    uploaded = client.post(
        "/api/resumes/upload",
        headers=owner_headers,
        files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")},
    )
    other_user_headers = authenticated_headers(client)

    class MustNotRun:
        def __init__(self):
            raise AssertionError("Analyzer must not run for a resume owned by another user")

    monkeypatch.setattr(resume_analysis_service, "ResumeAnalyzerAgent", MustNotRun)
    response = client.post(f"/api/resumes/{uploaded.json()['id']}/analyze", headers=other_user_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found"


def test_analyze_endpoint_sanitizes_provider_failure(client, monkeypatch):
    headers = authenticated_headers(client)
    uploaded = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")},
    )

    class FailedAnalyzer:
        model = "test-analyzer"

        async def analyze(self, _resume_text):
            raise AIProviderError("provider details must not reach the response")

    monkeypatch.setattr(resume_analysis_service, "ResumeAnalyzerAgent", FailedAnalyzer)
    response = client.post(f"/api/resumes/{uploaded.json()['id']}/analyze", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Resume analysis provider request failed."
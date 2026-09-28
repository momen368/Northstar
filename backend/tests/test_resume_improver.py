import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.agents.resume_improver import InvalidResumeImprovementError, ResumeImproverAgent
from backend.app.database.base import Base
from backend.app.database.dependencies import get_db
from backend.app.main import app
from backend.app.models import Resume, ResumeAnalysisRecord
from backend.app.rag.retriever import RetrievedChunk
from backend.app.schemas.resume_analysis import ResumeAnalysis
from backend.app.schemas.resume_improvement import ResumeImprovementDraft, ResumeImprovementResponse
import backend.app.services.resume_improvement_service as improvement_service


@pytest.fixture
def database(tmp_path):
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "improvement-tests.db")))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(database):
    def override_get_db():
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


class FakeLLM:
    def __init__(self, draft):
        self.draft = draft

    async def complete(self, *_args):
        return self.draft


def chunk():
    return RetrievedChunk(9, "Resume guide: quantify project results and list relevant credentials.",
                          0.88, "knowledge_base/resume_guidelines/guide.md", "Resume Guide",
                          "resume_guidelines", 0)


def test_improver_returns_resume_facts_and_cited_knowledge_recommendations():
    draft = ResumeImprovementDraft(
        strengths=["Lists Python and API experience"],
        weaknesses=["Project outcomes lack quantified results"],
        missing_skills=["Testing evidence"],
        improvements=["Add verified outcome measures to the API project bullet"],
        certifications=[{"text": "quantify project results", "source_ids": [9]}],
        learning_resources=[{"text": "Resume Guide", "source_ids": [9]}],
    )
    result = asyncio.run(ResumeImproverAgent(llm=FakeLLM(draft)).improve(
        "Python API developer", ResumeAnalysis(technical_skills=["Python"]), [chunk()],
    ))

    assert result.strengths == ["Lists Python and API experience"]
    assert result.improvements[0].startswith("Add verified")
    assert result.learning_resources == ["Resume Guide"]
    assert result.sources[0]["source"] == "knowledge_base/resume_guidelines/guide.md"


def test_improver_discards_knowledge_recommendations_without_retrieval():
    draft = ResumeImprovementDraft(
        improvements=["Clarify the existing project description"],
        certifications=[{"text": "Unsupported certification", "source_ids": [9]}],
    )
    result = asyncio.run(ResumeImproverAgent(llm=FakeLLM(draft)).improve(
        "Existing project details", ResumeAnalysis(), [],
    ))

    assert result.improvements == ["Clarify the existing project description"]
    assert result.certifications == []
    assert result.learning_resources == []
    assert result.sources == []


def test_improver_rejects_source_ids_outside_retrieved_chunks():
    draft = ResumeImprovementDraft(
        learning_resources=[{"text": "Unknown", "source_ids": [999]}],
    )
    with pytest.raises(InvalidResumeImprovementError):
        asyncio.run(ResumeImproverAgent(llm=FakeLLM(draft)).improve("Resume", ResumeAnalysis(), [chunk()]))


def register_and_login(client):
    email = f"improve-{uuid4().hex}@example.org"
    password = "SecurePassphrase123"
    client.post("/api/auth/register", json={"name": "Improvement User", "email": email, "password": password})
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_improvement_endpoint_handles_missing_resume_and_analysis(client, database):
    headers = register_and_login(client)
    assert client.post("/api/resumes/999/improve", headers=headers).status_code == 404
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    with database() as db:
        resume = Resume(user_id=user_id, original_filename="r.pdf", stored_filename=f"{uuid4().hex}.pdf",
                        file_type="pdf", extracted_text="Some resume text")
        db.add(resume)
        db.commit()
        resume_id = resume.id
    response = client.post(f"/api/resumes/{resume_id}/improve", headers=headers)
    assert response.status_code == 409


def test_improvement_endpoint_runs_with_analysis_and_returns_schema(client, database, monkeypatch):
    headers = register_and_login(client)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    with database() as db:
        resume = Resume(user_id=user_id, original_filename="r.pdf", stored_filename=f"{uuid4().hex}.pdf",
                        file_type="pdf", extracted_text="Python developer with API experience.")
        db.add(resume)
        db.flush()
        db.add(ResumeAnalysisRecord(resume_id=resume.id,
                                    result_json=ResumeAnalysis(technical_skills=["Python"]).model_dump(mode="json"),
                                    model_name="test"))
        db.commit()
        resume_id = resume.id

    class EmptyPipeline:
        def __init__(self, _db):
            pass

        async def retrieve(self, _query):
            return []

    class FakeImprover:
        async def improve(self, resume_text, analysis, _context):
            assert "Python developer" in resume_text
            assert analysis.technical_skills == ["Python"]
            return ResumeImprovementResponse(
                strengths=["Python experience"], weaknesses=[], missing_skills=[],
                improvements=["Clarify the existing API project."], certifications=[],
                learning_resources=[], sources=[],
            )

    monkeypatch.setattr(improvement_service, "RAGPipeline", EmptyPipeline)
    monkeypatch.setattr(improvement_service, "ResumeImproverAgent", lambda: FakeImprover())
    response = client.post(f"/api/resumes/{resume_id}/improve", headers=headers)

    assert response.status_code == 200
    assert response.json()["improvements"] == ["Clarify the existing API project."]
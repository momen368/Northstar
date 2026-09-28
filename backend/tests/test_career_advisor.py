import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.agents.career_advisor import CareerAdvisorAgent, InvalidCareerAdvisorResponseError
from backend.app.agents.structured_llm import LLMInvalidResponseError, LLMProviderError
from backend.app.database.base import Base
from backend.app.database.dependencies import get_db
from backend.app.main import app
from backend.app.models import Resume, ResumeAnalysisRecord
from backend.app.rag.retriever import RetrievedChunk
from backend.app.schemas.career_advisor import CareerAdvisorDraft
from backend.app.schemas.resume_analysis import ResumeAnalysis
import backend.app.services.career_advisor_service as advisor_service


@pytest.fixture
def isolated_database(tmp_path):
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "advisor-tests.db")))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(isolated_database):
    def override_get_db():
        with isolated_database() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def register_and_login(client):
    email = f"advisor-{uuid4().hex}@example.org"
    password = "SecurePassphrase123"
    assert client.post("/api/auth/register", json={
        "name": "Advisor Tester", "email": email, "password": password,
    }).status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_resume_with_analysis(client, factory, headers):
    profile = client.get("/api/auth/me", headers=headers).json()
    with factory() as db:
        resume = Resume(
            user_id=profile["id"], original_filename="resume.pdf", stored_filename=f"{uuid4().hex}.pdf",
            file_type="pdf", extracted_text="Python developer with API experience.",
        )
        db.add(resume)
        db.flush()
        db.add(ResumeAnalysisRecord(
            resume_id=resume.id,
            result_json=ResumeAnalysis(summary="Python developer", technical_skills=["Python"]).model_dump(mode="json"),
            model_name="test",
        ))
        db.commit()
        return resume.id


class FakeLLM:
    def __init__(self, draft=None, error=None):
        self.draft = draft
        self.error = error
        self.user_prompt = ""

    async def complete(self, _system, user_prompt, _schema):
        self.user_prompt = user_prompt
        if self.error:
            raise self.error
        return self.draft


def source_chunk(chunk_id=4):
    return RetrievedChunk(
        id=chunk_id,
        content="Python course: Practical Python APIs. Provider: Skills Academy.",
        score=0.92,
        source="knowledge_base/learning_resources/python.md",
        title="Practical Python APIs",
        category="learning_resources",
        chunk_index=0,
    )


def test_advisor_uses_analysis_and_retrieval_and_returns_cited_suggestions():
    draft = CareerAdvisorDraft(
        answer="Your API experience aligns with the retrieved Python learning path.",
        skill_gaps=["API testing"],
        recommended_courses=[{"text": "Practical Python APIs", "source_ids": [4]}],
        certifications=[],
        learning_resources=[{"text": "Skills Academy", "source_ids": [4]}],
        roadmap=[{"text": "Complete Practical Python APIs", "source_ids": [4]}],
    )
    llm = FakeLLM(draft=draft)
    result = __import__("asyncio").run(CareerAdvisorAgent(llm=llm).answer(
        "How can I improve?",
        ResumeAnalysis(summary="Python developer", technical_skills=["Python"]),
        [source_chunk()],
    ))
    prompt = json.loads(llm.user_prompt)

    assert prompt["resume_analysis"]["technical_skills"] == ["Python"]
    assert prompt["retrieved_context"][0]["id"] == 4
    assert result.recommended_courses == ["Practical Python APIs"]
    assert result.sources[0].source == "knowledge_base/learning_resources/python.md"


def test_empty_context_forces_explicit_limitation_and_no_resources():
    draft = CareerAdvisorDraft(
        answer="I can discuss your experience at a high level.",
        recommended_courses=[{"text": "Invented course", "source_ids": [4]}],
    )
    result = __import__("asyncio").run(CareerAdvisorAgent(llm=FakeLLM(draft=draft)).answer(
        "Recommend a course", ResumeAnalysis(), [],
    ))

    assert "knowledge base does not contain enough" in result.answer.casefold()
    assert result.recommended_courses == []
    assert result.certifications == []
    assert result.learning_resources == []
    assert result.roadmap == []
    assert result.sources == []


def test_agent_rejects_source_ids_not_in_retrieval():
    draft = CareerAdvisorDraft(
        answer="This is based on a source.",
        certifications=[{"text": "Credential", "source_ids": [999]}],
    )
    with pytest.raises(InvalidCareerAdvisorResponseError):
        __import__("asyncio").run(CareerAdvisorAgent(llm=FakeLLM(draft=draft)).answer(
            "Which certification?", ResumeAnalysis(), [source_chunk()],
        ))


def test_endpoint_handles_missing_resume_and_missing_analysis(client, isolated_database):
    headers = register_and_login(client)
    assert client.post("/api/career-advisor", headers=headers,
                       json={"resume_id": 999, "question": "What should I learn next?"}).status_code == 404
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    with isolated_database() as db:
        resume = Resume(user_id=user_id, original_filename="r.pdf", stored_filename=f"{uuid4().hex}.pdf",
                        file_type="pdf", extracted_text="Not analyzed.")
        db.add(resume)
        db.commit()
        resume_id = resume.id
    response = client.post("/api/career-advisor", headers=headers,
                           json={"resume_id": resume_id, "question": "What should I learn next?"})
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(LLMProviderError("private provider detail"), 502),
     (LLMInvalidResponseError("private malformed response"), 502)],
)
def test_endpoint_sanitizes_ai_failure_and_invalid_output(client, isolated_database, monkeypatch, error,
                                                           expected_status):
    headers = register_and_login(client)
    resume_id = create_resume_with_analysis(client, isolated_database, headers)

    class EmptyPipeline:
        def __init__(self, _db):
            pass

        async def retrieve(self, _query):
            return []

    class FailedAdvisor:
        def __init__(self):
            pass

        async def answer(self, *_args):
            raise error

    monkeypatch.setattr(advisor_service, "RAGPipeline", EmptyPipeline)
    monkeypatch.setattr(advisor_service, "CareerAdvisorAgent", FailedAdvisor)
    response = client.post("/api/career-advisor", headers=headers,
                           json={"resume_id": resume_id, "question": "What should I learn next?"})

    assert response.status_code == expected_status
    assert "private" not in response.text
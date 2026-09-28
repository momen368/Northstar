from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.agents.structured_llm import LLMInvalidResponseError, LLMProviderError
from backend.app.agents.job_matching import JobMatchingAgent
from backend.app.database.base import Base
from backend.app.database.dependencies import get_db
from backend.app.main import app
from backend.app.models import Job, JobSkill, Resume, ResumeAnalysisRecord, Skill
from backend.app.schemas.job_matching import MatchNarrative
from backend.app.schemas.resume_analysis import EducationEntry, ExperienceEntry, ResumeAnalysis
import backend.app.services.job_matching_service as matching_service


@pytest.fixture
def database(tmp_path):
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "matching-tests.db")))
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


class NarrativeLLM:
    async def complete(self, *_args):
        return MatchNarrative(explanation="The score reflects direct skill coverage and related experience.",
                              recommendation="Address the listed gaps before applying.")


def build_job(skills, description="Build Python APIs and maintain software systems."):
    job = Job(title="Python Engineer", company="Example", description=description, experience_level="senior")
    job.job_skills = [JobSkill(skill=Skill(name=name, category="general"), importance=1.0) for name in skills]
    return job


def test_strong_partial_and_no_skill_matches_are_deterministic():
    agent = JobMatchingAgent(llm=NarrativeLLM())
    strong_analysis = ResumeAnalysis(
        summary="Build Python APIs and maintain software systems.",
        technical_skills=["Python", "SQL"],
        experience=[ExperienceEntry(position="Python Engineer", company="Example", responsibilities=["Build APIs"] )],
        education=[EducationEntry(degree="Bachelor of Computer Science")],
    )
    job = build_job(["Python", "SQL"], "Build Python APIs. Bachelor degree preferred.")
    strong = __import__("asyncio").run(agent.match(strong_analysis, job))
    partial = __import__("asyncio").run(agent.match(
        ResumeAnalysis(summary="Support business users.", technical_skills=["Python"]), build_job(["Python", "SQL"])
    ))
    none = __import__("asyncio").run(agent.match(
        ResumeAnalysis(summary="Retail associate.", technical_skills=["Cash handling"]), build_job(["Python", "SQL"])
    ))

    assert strong.match_score > partial.match_score > none.match_score
    assert strong.matched_skills == ["Python", "SQL"]
    assert strong.missing_skills == []
    assert partial.matched_skills == ["Python"]
    assert partial.missing_skills == ["SQL"]
    assert none.match_score >= 0


def register_and_login(client):
    email = f"match-{uuid4().hex}@example.org"
    password = "SecurePassphrase123"
    client.post("/api/auth/register", json={"name": "Matcher", "email": email, "password": password})
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_resume_and_job(client, database, headers, skills=("Python", "SQL")):
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    with database() as db:
        resume = Resume(user_id=user_id, original_filename="resume.pdf", stored_filename=f"{uuid4().hex}.pdf",
                        file_type="pdf", extracted_text="Python engineer who builds APIs.")
        db.add(resume)
        db.flush()
        db.add(ResumeAnalysisRecord(
            resume_id=resume.id,
            result_json=ResumeAnalysis(summary="Python engineer who builds APIs.", technical_skills=["Python"]).model_dump(mode="json"),
            model_name="test",
        ))
        db.commit()
        resume_id = resume.id
    response = client.post("/api/jobs", headers=headers, json={
        "title": "Python Engineer", "company": "Example", "location": "Remote",
        "description": "Build Python APIs and maintain software systems.",
        "experience_level": "mid", "skills": list(skills),
    })
    assert response.status_code == 201
    return resume_id, response.json()["id"]


def test_endpoint_matches_and_persists_recommendation_then_lists_sorted(client, database, monkeypatch):
    headers = register_and_login(client)
    resume_id, first_job_id = create_resume_and_job(client, database, headers, ("Python", "SQL"))
    _, second_job_id = create_resume_and_job(client, database, headers, ("Python",))

    class FakeAgent:
        async def match(self, analysis, job):
            score = 90 if len(job.job_skills) == 1 else 55
            return __import__("backend.app.schemas.job_matching", fromlist=["JobMatchResult"]).JobMatchResult(
                match_score=score,
                matched_skills=["Python"],
                missing_skills=["SQL"] if len(job.job_skills) > 1 else [],
                explanation="Score is based on listed skills and resume evidence.",
                recommendation="Consider demonstrating SQL experience." if len(job.job_skills) > 1 else "Apply with confidence.",
                score_breakdown={"technical_skill_coverage": 0.5, "experience_relevance": 0.5},
            )

    monkeypatch.setattr(matching_service, "JobMatchingAgent", FakeAgent)
    first = client.post("/api/recommendations/match", headers=headers,
                        json={"resume_id": resume_id, "job_id": first_job_id})
    second = client.post("/api/recommendations/match", headers=headers,
                         json={"resume_id": resume_id, "job_id": second_job_id})

    assert first.status_code == 201
    assert first.json()["missing_skills"] == ["SQL"]
    assert second.status_code == 201
    listed = client.get(f"/api/recommendations/{resume_id}", headers=headers)
    assert listed.status_code == 200
    assert [item["match_score"] for item in listed.json()] == [90, 55]


def test_endpoint_reports_missing_analysis_and_job(client, database):
    headers = register_and_login(client)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    with database() as db:
        resume = Resume(user_id=user_id, original_filename="resume.pdf", stored_filename=f"{uuid4().hex}.pdf",
                        file_type="pdf", extracted_text="Python engineer")
        db.add(resume)
        db.commit()
        resume_id = resume.id
    assert client.post("/api/recommendations/match", headers=headers,
                       json={"resume_id": resume_id, "job_id": 1}).status_code == 404

    _, job_id = create_resume_and_job(client, database, headers)
    missing_analysis_resume = Resume(user_id=user_id, original_filename="other.pdf",
                                     stored_filename=f"{uuid4().hex}.pdf", file_type="pdf", extracted_text="text")
    with database() as db:
        db.add(missing_analysis_resume)
        db.commit()
        missing_id = missing_analysis_resume.id
    response = client.post("/api/recommendations/match", headers=headers,
                           json={"resume_id": missing_id, "job_id": job_id})
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(LLMProviderError("secret provider failure"), 502),
     (LLMInvalidResponseError("secret invalid response"), 502)],
)
def test_endpoint_sanitizes_ai_failures(client, database, monkeypatch, error, expected_status):
    headers = register_and_login(client)
    resume_id, job_id = create_resume_and_job(client, database, headers)

    class BrokenAgent:
        async def match(self, *_args):
            raise error

    monkeypatch.setattr(matching_service, "JobMatchingAgent", BrokenAgent)
    response = client.post("/api/recommendations/match", headers=headers,
                           json={"resume_id": resume_id, "job_id": job_id})

    assert response.status_code == expected_status
    assert "secret" not in response.text
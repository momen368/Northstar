from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.database.engine import engine
from backend.app.database.session import SessionLocal
from backend.app.main import app
from backend.app.models import (
    AuthSession,
    CareerRecommendation,
    Job,
    JobSkill,
    Recommendation,
    Resume,
    ResumeSkill,
    Skill,
    User,
)
from backend.app.utils.passwords import verify_password


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_response(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AI Resume Analyzer API",
    }
    assert client.get("/api/auth/me").status_code == 401


def test_swagger_and_openapi_are_available(client):
    docs_response = client.get("/docs")
    schema_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text.lower()
    assert schema_response.status_code == 200
    assert "/api/health" in schema_response.json()["paths"]


def test_startup_creates_tables_and_database_health_works(client):
    response = client.get("/api/health/database")
    tables = set(inspect(engine).get_table_names())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    assert tables == {
        "users",
        "auth_sessions",
        "resumes",
        "resume_analyses",
        "skills",
        "resume_skills",
        "jobs",
        "job_skills",
        "recommendations",
        "career_recommendations",
        "knowledge_chunks",
    }


def test_models_persist_and_follow_relationships(tmp_path):
    test_engine = create_engine(URL.create("sqlite", database=str(tmp_path / "relationships.db")))
    Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, expire_on_commit=False)()
    try:
        user = User(name="Test User", email="relationships@example.org", password_hash="placeholder")
        resume = Resume(
            original_filename="resume.pdf",
            stored_filename="stored-resume.pdf",
            file_type="pdf",
        )
        skill = Skill(name="Python", category="programming")
        resume.resume_skills.append(ResumeSkill(skill=skill, confidence=0.95))

        job = Job(
            title="Engineer",
            company="Example",
            description="Build software.",
            experience_level="mid",
        )
        job.job_skills.append(JobSkill(skill=skill, importance=1.0))
        resume.job_recommendations.append(
            Recommendation(job=job, match_score=87.5, explanation="Strong fit")
        )
        resume.career_recommendations.append(
            CareerRecommendation(
                recommendation_type="learning",
                title="Practice SQL",
                description="Build a small database project.",
            )
        )
        user.resumes.append(resume)
        test_session.add(user)
        test_session.commit()

        assert resume.user.email == "relationships@example.org"
        assert resume.resume_skills[0].skill.name == "Python"
        assert job.job_skills[0].skill.category == "programming"
        assert resume.job_recommendations[0].job.company == "Example"
        assert resume.career_recommendations[0].resume_id == resume.id
        resume_foreign_keys = inspect(test_engine).get_foreign_keys("resumes")
        assert any(item["referred_table"] == "users" for item in resume_foreign_keys)
    finally:
        test_session.close()
        test_engine.dispose()


def account_payload(email: str | None = None, password: str = "SecurePassphrase123") -> dict[str, str]:
    return {
        "name": "  Example   User ",
        "email": email or f"user-{uuid4().hex}@example.org",
        "password": password,
    }


def test_successful_registration_hashes_password_and_returns_public_user(client):
    payload = account_payload()
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["name"] == "Example User"
    assert response.json()["email"] == payload["email"]
    assert "password_hash" not in response.json()
    assert "password" not in response.json()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == payload["email"]))
        assert user is not None
        assert user.password_hash != payload["password"]
        assert verify_password(payload["password"], user.password_hash)


def test_duplicate_registration_returns_conflict(client):
    payload = account_payload()
    assert client.post("/api/auth/register", json=payload).status_code == 201

    duplicate_response = client.post("/api/auth/register", json=payload)

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Email is already registered"


@pytest.mark.parametrize(
    ("email", "password"),
    [("not-an-email", "SecurePassphrase123"), ("weak@example.org", "short1")],
)
def test_invalid_email_and_weak_password_are_rejected_without_echoing_password(client, email, password):
    response = client.post("/api/auth/register", json=account_payload(email, password))

    assert response.status_code == 422
    assert password not in response.text


def test_successful_login_and_current_user(client):
    payload = account_payload()
    assert client.post("/api/auth/register", json=payload).status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["token_type"] == "bearer"
    assert login_data["expires_in"] > 0
    assert login_data["access_token"]
    assert "password_hash" not in login_data["user"]
    with SessionLocal() as db:
        stored_session = db.scalar(
            select(AuthSession).where(AuthSession.user_id == login_data["user"]["id"])
        )
        assert stored_session is not None
        assert stored_session.token_hash != login_data["access_token"]
        assert len(stored_session.token_hash) == 64

    current_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert current_response.status_code == 200
    assert current_response.json()["email"] == payload["email"]
    assert "password_hash" not in current_response.json()


def test_invalid_password_is_rejected(client):
    payload = account_payload()
    assert client.post("/api/auth/register", json=payload).status_code == 201

    response = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": "WrongPassword123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_unauthenticated_current_user_request_is_rejected(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_logout_revokes_authenticated_session(client):
    payload = account_payload()
    client.post("/api/auth/register", json=payload)
    login_response = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/api/auth/logout", headers=headers)

    assert logout_response.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
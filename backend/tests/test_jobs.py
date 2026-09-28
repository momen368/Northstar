from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.database.dependencies import get_db
from backend.app.main import app
from backend.app.models import Job, JobSkill


@pytest.fixture
def isolated_database(tmp_path):
    test_engine = create_engine(URL.create("sqlite", database=str(tmp_path / "jobs-tests.db")))
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    yield session_factory
    test_engine.dispose()


@pytest.fixture
def client(isolated_database):
    def override_get_db():
        with isolated_database() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def authenticated_headers(client: TestClient) -> dict[str, str]:
    email = f"jobs-{uuid4().hex}@example.org"
    password = "SecurePassphrase123"
    registered = client.post(
        "/api/auth/register",
        json={"name": "Job Owner", "email": email, "password": password},
    )
    assert registered.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def job_payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Senior Python Engineer",
        "company": "Northstar Labs",
        "location": "Toronto, Canada",
        "description": "Build reliable APIs and data services for customer products.",
        "experience_level": "senior",
        "skills": ["Python", "SQL", "Python"],
    }
    payload.update(overrides)
    return payload


def test_create_job_persists_job_skill_relationships(client, isolated_database):
    headers = authenticated_headers(client)
    response = client.post("/api/jobs", headers=headers, json=job_payload())

    assert response.status_code == 201
    result = response.json()
    assert result["title"] == "Senior Python Engineer"
    assert result["skills"] == ["Python", "SQL"]
    with isolated_database() as db:
        stored_job = db.get(Job, result["id"])
        assert stored_job is not None
        assert stored_job.owner_id is not None
        assert {association.skill.name for association in stored_job.job_skills} == {"Python", "SQL"}


def test_read_list_update_and_delete_job(client):
    headers = authenticated_headers(client)
    created = client.post("/api/jobs", headers=headers, json=job_payload()).json()
    job_id = created["id"]

    detail = client.get(f"/api/jobs/{job_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["company"] == "Northstar Labs"

    listing = client.get("/api/jobs?limit=5&offset=0", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == job_id

    updated = client.put(
        f"/api/jobs/{job_id}",
        headers=headers,
        json=job_payload(title="Staff Python Engineer", skills=["Python", "Cloud"]),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Staff Python Engineer"
    assert updated.json()["skills"] == ["Python", "Cloud"]

    deleted = client.delete(f"/api/jobs/{job_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 404


def test_search_filters_keyword_location_experience_and_skill_and_paginates(client):
    headers = authenticated_headers(client)
    client.post("/api/jobs", headers=headers, json=job_payload())
    client.post(
        "/api/jobs",
        headers=headers,
        json=job_payload(
            title="Junior Data Analyst",
            company="Contoso",
            location="Remote",
            experience_level="entry-level",
            skills=["Excel", "SQL"],
        ),
    )

    response = client.get(
        "/api/jobs/search",
        headers=headers,
        params={"keyword": "Python", "location": "Toronto", "experience_level": "senior", "skill": "Python"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["company"] == "Northstar Labs"

    skill_response = client.get("/api/jobs/search?skill=SQL", headers=headers)
    assert skill_response.json()["total"] == 2

    page = client.get("/api/jobs?limit=1&offset=1", headers=headers)
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1


@pytest.mark.parametrize(
    "invalid_payload",
    [
        job_payload(title=" "),
        job_payload(company=""),
        job_payload(description="short"),
        job_payload(skills=[""]),
        job_payload(skills=["x" * 121]),
        job_payload(skills=["Python"] * 51),
    ],
)
def test_invalid_job_data_is_rejected(client, invalid_payload):
    response = client.post("/api/jobs", headers=authenticated_headers(client), json=invalid_payload)

    assert response.status_code == 422


def test_missing_job_returns_404_for_read_update_and_delete(client):
    headers = authenticated_headers(client)

    assert client.get("/api/jobs/99999", headers=headers).status_code == 404
    assert client.put("/api/jobs/99999", headers=headers, json=job_payload()).status_code == 404
    assert client.delete("/api/jobs/99999", headers=headers).status_code == 404


def test_unauthorized_job_operations_return_401(client):
    payload = job_payload()

    assert client.post("/api/jobs", json=payload).status_code == 401
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs/search").status_code == 401
    assert client.get("/api/jobs/1").status_code == 401
    assert client.put("/api/jobs/1", json=payload).status_code == 401
    assert client.delete("/api/jobs/1").status_code == 401


def test_user_cannot_read_update_or_delete_another_users_job(client):
    owner_headers = authenticated_headers(client)
    created = client.post("/api/jobs", headers=owner_headers, json=job_payload()).json()
    other_headers = authenticated_headers(client)
    job_id = created["id"]

    assert client.get("/api/jobs", headers=other_headers).json()["items"] == []
    assert client.get(f"/api/jobs/{job_id}", headers=other_headers).status_code == 404
    assert client.put(f"/api/jobs/{job_id}", headers=other_headers, json=job_payload()).status_code == 404
    assert client.delete(f"/api/jobs/{job_id}", headers=other_headers).status_code == 404
    assert client.get("/api/jobs/search?keyword=Python", headers=other_headers).json()["items"] == []
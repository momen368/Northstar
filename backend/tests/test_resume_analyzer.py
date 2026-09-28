import asyncio
import json

import httpx
import pytest

from backend.app.agents.resume_analyzer import (
    AIProviderError,
    InvalidAIResponseError,
    ResumeAnalyzerAgent,
)


def response_transport(content: str, status_code: int = 200) -> httpx.AsyncBaseTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        if status_code >= 400:
            return httpx.Response(status_code, json={"error": "provider failure"})
        return httpx.Response(status_code, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def analyzer(content: str, status_code: int = 200) -> ResumeAnalyzerAgent:
    return ResumeAnalyzerAgent(
        base_url="https://provider.example/v1",
        model="test-model",
        api_key="test-secret-never-return-this",
        transport=response_transport(content, status_code),
    )


def run_analysis(agent: ResumeAnalyzerAgent, resume_text: str):
    return asyncio.run(agent.analyze(resume_text))


def test_analyzes_normal_resume_into_structured_data():
    structured = {
        "personal_information": {"full_name": "Avery Chen", "email": "avery@example.org"},
        "summary": "Backend engineer with Python experience.",
        "education": [{"institution": "Example University", "degree": "BSc"}],
        "experience": [{"position": "Developer", "company": "Example Co", "responsibilities": ["Built APIs"]}],
        "technical_skills": ["Python", "SQL"],
        "soft_skills": ["Communication"],
        "projects": [{"name": "Inventory tool", "technologies": ["Python"]}],
        "certifications": [{"name": "Cloud Fundamentals"}],
        "languages": [{"name": "English", "proficiency": "Fluent"}],
        "other_sections": [],
    }
    result = run_analysis(analyzer(json.dumps(structured)), "Avery Chen, Python backend engineer")

    assert result.personal_information.full_name == "Avery Chen"
    assert result.experience[0].responsibilities == ["Built APIs"]
    assert result.technical_skills == ["Python", "SQL"]


def test_missing_sections_default_to_null_or_empty_lists():
    result = run_analysis(analyzer('{"summary":"Concise profile."}'), "A concise profile.")

    assert result.summary == "Concise profile."
    assert result.personal_information is None
    assert result.education == []
    assert result.experience == []
    assert result.projects == []
    assert result.certifications == []
    assert result.languages == []


def test_very_short_resume_is_still_analyzed_without_inventing_sections():
    result = run_analysis(analyzer('{"technical_skills":["Python"]}'), "Python")

    assert result.technical_skills == ["Python"]
    assert result.summary is None
    assert result.education == []
    assert result.experience == []


def test_invalid_ai_json_is_reported_without_exposing_provider_data():
    with pytest.raises(InvalidAIResponseError, match="invalid structured data") as error:
        run_analysis(analyzer("not-json"), "Resume text")

    assert "test-secret-never-return-this" not in str(error.value)


def test_ai_api_failure_is_reported_without_exposing_secret():
    with pytest.raises(AIProviderError, match="request failed") as error:
        run_analysis(analyzer("{}", status_code=503), "Resume text")

    assert "test-secret-never-return-this" not in str(error.value)
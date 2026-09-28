from pydantic import BaseModel, ConfigDict, Field


class MatchRequest(BaseModel):
    resume_id: int = Field(gt=0)
    job_id: int = Field(gt=0)


class MatchNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(min_length=10, max_length=3000)
    recommendation: str = Field(min_length=10, max_length=2000)


class ScoreBreakdown(BaseModel):
    technical_skill_coverage: float = Field(ge=0, le=1)
    experience_relevance: float = Field(ge=0, le=1)
    education_relevance: float | None = Field(default=None, ge=0, le=1)


class JobMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str
    recommendation: str
    score_breakdown: ScoreBreakdown


class RecommendationResponse(JobMatchResult):
    id: int
    resume_id: int
    job_id: int
    job_title: str
    company: str
    created_at: str
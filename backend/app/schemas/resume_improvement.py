from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.career_advisor import GroundedSuggestion


class ResumeImprovementDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[str] = Field(default_factory=list, max_length=30)
    weaknesses: list[str] = Field(default_factory=list, max_length=30)
    missing_skills: list[str] = Field(default_factory=list, max_length=50)
    improvements: list[str] = Field(default_factory=list, max_length=50)
    certifications: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)
    learning_resources: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)


class ResumeImprovementResponse(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    missing_skills: list[str]
    improvements: list[str]
    certifications: list[str]
    learning_resources: list[str]
    sources: list[dict[str, object]]
from pydantic import BaseModel, ConfigDict, Field


class GroundedSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=2, max_length=1000)
    source_ids: list[int] = Field(min_length=1, max_length=10)


class CareerAdvisorDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=10, max_length=6000)
    skill_gaps: list[str] = Field(default_factory=list, max_length=50)
    recommended_courses: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)
    certifications: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)
    learning_resources: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)
    roadmap: list[GroundedSuggestion] = Field(default_factory=list, max_length=30)


class CareerSource(BaseModel):
    id: int
    title: str
    source: str
    category: str
    chunk_index: int


class CareerAdvisorResponse(BaseModel):
    answer: str
    skill_gaps: list[str]
    recommended_courses: list[str]
    certifications: list[str]
    learning_resources: list[str]
    roadmap: list[str]
    sources: list[CareerSource]
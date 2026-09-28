from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobFields(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=200)
    description: str = Field(min_length=10, max_length=30000)
    experience_level: str = Field(default="unspecified", min_length=2, max_length=80)
    skills: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("title", "company", "description", "experience_level")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("location")
    @classmethod
    def trim_location(cls, value: str) -> str:
        return value.strip()

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for value in values:
            skill = value.strip()
            if not skill:
                raise ValueError("Skills cannot contain blank values")
            if len(skill) > 120:
                raise ValueError("Each skill must be 120 characters or fewer")
            key = skill.casefold()
            if key not in seen:
                normalized.append(skill)
                seen.add(key)
        return normalized


class JobCreate(JobFields):
    pass


class JobUpdate(JobFields):
    pass


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str
    description: str
    experience_level: str
    skills: list[str]
    created_at: datetime
    updated_at: datetime


class JobPage(BaseModel):
    items: list[JobResponse]
    total: int
    limit: int
    offset: int
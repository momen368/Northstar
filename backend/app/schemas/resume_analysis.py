from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonalInformation(AnalysisEntry):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    website: str | None = None


class EducationEntry(AnalysisEntry):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)


class ExperienceEntry(AnalysisEntry):
    position: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: list[str] = Field(default_factory=list)


class ProjectEntry(AnalysisEntry):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class CertificationEntry(AnalysisEntry):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None


class LanguageEntry(AnalysisEntry):
    name: str | None = None
    proficiency: str | None = None


class OtherSection(AnalysisEntry):
    title: str | None = None
    content: list[str] = Field(default_factory=list)


class ResumeAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personal_information: PersonalInformation | None = None
    summary: str | None = None
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    other_sections: list[OtherSection] = Field(default_factory=list)


class ResumeAnalysisResponse(BaseModel):
    id: int
    resume_id: int
    result: ResumeAnalysis
    model_name: str
    created_at: datetime
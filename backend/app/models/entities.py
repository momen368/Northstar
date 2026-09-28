from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)

    resumes: Mapped[list[Resume]] = relationship(back_populates="user", cascade="all, delete-orphan")
    auth_sessions: Mapped[list[AuthSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list[Job]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="auth_sessions")


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user: Mapped[User] = relationship(back_populates="resumes")
    resume_skills: Mapped[list[ResumeSkill]] = relationship(back_populates="resume", cascade="all, delete-orphan")
    job_recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    career_recommendations: Mapped[list[CareerRecommendation]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    analyses: Mapped[list[ResumeAnalysisRecord]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeAnalysisRecord(CreatedAtMixin, Base):
    __tablename__ = "resume_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), default="resume-analysis-v1", nullable=False)

    resume: Mapped[Resume] = relationship(back_populates="analyses")


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("name", "category", name="uq_skill_name_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)

    resume_skills: Mapped[list[ResumeSkill]] = relationship(back_populates="skill", cascade="all, delete-orphan")
    job_skills: Mapped[list[JobSkill]] = relationship(back_populates="skill", cascade="all, delete-orphan")
    resumes: Mapped[list[Resume]] = relationship(secondary="resume_skills", viewonly=True)
    jobs: Mapped[list[Job]] = relationship(secondary="job_skills", viewonly=True)


class ResumeSkill(Base):
    __tablename__ = "resume_skills"
    __table_args__ = (CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_resume_skill_confidence"),)

    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    resume: Mapped[Resume] = relationship(back_populates="resume_skills")
    skill: Mapped[Skill] = relationship(back_populates="resume_skills")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    experience_level: Mapped[str] = mapped_column(String(80), default="unspecified", nullable=False)

    owner: Mapped[User | None] = relationship(back_populates="jobs")
    job_skills: Mapped[list[JobSkill]] = relationship(back_populates="job", cascade="all, delete-orphan")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (CheckConstraint("importance >= 0", name="ck_job_skill_importance"),)

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    importance: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    job: Mapped[Job] = relationship(back_populates="job_skills")
    skill: Mapped[Skill] = relationship(back_populates="job_skills")


class Recommendation(CreatedAtMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("match_score >= 0 AND match_score <= 100", name="ck_recommendation_match_score"),
        UniqueConstraint("resume_id", "job_id", name="uq_recommendation_resume_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, object] | None] = mapped_column(JSON)

    resume: Mapped[Resume] = relationship(back_populates="job_recommendations")
    job: Mapped[Job] = relationship(back_populates="recommendations")


class CareerRecommendation(CreatedAtMixin, Base):
    __tablename__ = "career_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    resume: Mapped[Resume] = relationship(back_populates="career_recommendations")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("source", "chunk_index", name="uq_knowledge_source_chunk"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
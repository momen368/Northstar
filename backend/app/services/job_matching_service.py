from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.agents.job_matching import JobMatchingAgent
from backend.app.models import Job, JobSkill, Recommendation, Resume, ResumeAnalysisRecord
from backend.app.schemas.job_matching import JobMatchResult
from backend.app.schemas.resume_analysis import ResumeAnalysis


class MatchResourceNotFoundError(Exception):
    pass


class MissingResumeAnalysisError(Exception):
    pass


async def match_resume_to_job(db: Session, user_id: int, resume_id: int, job_id: int) -> tuple[Recommendation, Job]:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise MatchResourceNotFoundError("Resume not found")
    job = db.scalar(
        select(Job).where(Job.id == job_id, Job.owner_id == user_id)
        .options(selectinload(Job.job_skills).selectinload(JobSkill.skill))
    )
    if job is None:
        raise MatchResourceNotFoundError("Job not found")
    analysis_record = db.scalar(
        select(ResumeAnalysisRecord).where(ResumeAnalysisRecord.resume_id == resume_id)
        .order_by(ResumeAnalysisRecord.created_at.desc(), ResumeAnalysisRecord.id.desc())
    )
    if analysis_record is None:
        raise MissingResumeAnalysisError
    analysis = ResumeAnalysis.model_validate(analysis_record.result_json)
    result = await JobMatchingAgent().match(analysis, job)
    recommendation = db.scalar(
        select(Recommendation).where(Recommendation.resume_id == resume_id, Recommendation.job_id == job_id)
    )
    if recommendation is None:
        recommendation = Recommendation(resume_id=resume_id, job_id=job_id, match_score=result.match_score,
                                        explanation=result.explanation, details_json=result.model_dump(mode="json"))
        db.add(recommendation)
    else:
        recommendation.match_score = result.match_score
        recommendation.explanation = result.explanation
        recommendation.details_json = result.model_dump(mode="json")
    db.commit()
    db.refresh(recommendation)
    return recommendation, job


def list_resume_recommendations(db: Session, user_id: int, resume_id: int) -> list[tuple[Recommendation, Job]]:
    owned_resume = db.scalar(select(Resume.id).where(Resume.id == resume_id, Resume.user_id == user_id))
    if owned_resume is None:
        raise MatchResourceNotFoundError("Resume not found")
    rows = db.execute(
        select(Recommendation, Job).join(Job, Job.id == Recommendation.job_id)
        .where(Recommendation.resume_id == resume_id, Job.owner_id == user_id)
        .order_by(Recommendation.match_score.desc(), Recommendation.created_at.desc())
    )
    return list(rows)
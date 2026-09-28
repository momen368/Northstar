from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.career_advisor import CareerAdvisorAgent
from backend.app.models import ResumeAnalysisRecord
from backend.app.rag.pipeline import RAGPipeline
from backend.app.services.resume_service import ResumeNotFoundError, get_user_resume
from backend.app.schemas.career_advisor import CareerAdvisorResponse
from backend.app.schemas.resume_analysis import ResumeAnalysis


class MissingResumeAnalysisError(Exception):
    pass


async def get_career_advice(
    db: Session,
    user_id: int,
    resume_id: int,
    question: str,
) -> CareerAdvisorResponse:
    resume = get_user_resume(db, user_id, resume_id)
    analysis_record = db.scalar(
        select(ResumeAnalysisRecord).where(ResumeAnalysisRecord.resume_id == resume.id)
        .order_by(ResumeAnalysisRecord.created_at.desc(), ResumeAnalysisRecord.id.desc())
    )
    if analysis_record is None:
        raise MissingResumeAnalysisError
    analysis = ResumeAnalysis.model_validate(analysis_record.result_json)
    query = " ".join(filter(None, [question, analysis.summary, *analysis.technical_skills]))
    context = await RAGPipeline(db).retrieve(query)
    return await CareerAdvisorAgent().answer(question, analysis, context)
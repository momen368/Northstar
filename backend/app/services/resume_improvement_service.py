from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.resume_improver import ResumeImproverAgent
from backend.app.models import ResumeAnalysisRecord
from backend.app.rag.pipeline import RAGPipeline
from backend.app.schemas.resume_analysis import ResumeAnalysis
from backend.app.schemas.resume_improvement import ResumeImprovementResponse
from backend.app.services.resume_service import get_user_resume


class MissingResumeAnalysisError(Exception):
    pass


async def improve_user_resume(
    db: Session,
    user_id: int,
    resume_id: int,
) -> ResumeImprovementResponse:
    resume = get_user_resume(db, user_id, resume_id)
    analysis_record = db.scalar(
        select(ResumeAnalysisRecord).where(ResumeAnalysisRecord.resume_id == resume.id)
        .order_by(ResumeAnalysisRecord.created_at.desc(), ResumeAnalysisRecord.id.desc())
    )
    if analysis_record is None:
        raise MissingResumeAnalysisError
    analysis = ResumeAnalysis.model_validate(analysis_record.result_json)
    query = " ".join(filter(None, ["resume writing improvement", analysis.summary, *analysis.technical_skills]))
    context = await RAGPipeline(db).retrieve(query)
    return await ResumeImproverAgent().improve(resume.extracted_text, analysis, context)
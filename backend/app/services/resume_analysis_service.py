from sqlalchemy.orm import Session

from backend.app.agents.resume_analyzer import ResumeAnalyzerAgent
from backend.app.models import ResumeAnalysisRecord
from backend.app.services.resume_service import ResumeNotFoundError, get_user_resume


class ResumeTextUnavailableError(ValueError):
    pass


async def analyze_user_resume(db: Session, user_id: int, resume_id: int) -> ResumeAnalysisRecord:
    resume = get_user_resume(db, user_id, resume_id)
    if not resume.extracted_text.strip():
        raise ResumeTextUnavailableError("Resume has no extracted text to analyze.")

    analyzer = ResumeAnalyzerAgent()
    result = await analyzer.analyze(resume.extracted_text)
    record = ResumeAnalysisRecord(
        resume_id=resume.id,
        result_json=result.model_dump(mode="json"),
        model_name=analyzer.model,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
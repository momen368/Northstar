from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import settings
from backend.app.database.dependencies import get_db
from backend.app.models import User
from backend.app.schemas.resume import ResumeResponse, ResumeUploadResponse
from backend.app.schemas.resume_analysis import ResumeAnalysis, ResumeAnalysisResponse
from backend.app.agents.resume_analyzer import (
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
    InvalidAIResponseError,
)
from backend.app.services.resume_service import (
    ResumeNotFoundError,
    create_resume,
    delete_user_resume,
    get_user_resume,
    list_user_resumes,
)
from backend.app.services.resume_parser import ResumeParserError
from backend.app.services.resume_analysis_service import (
    ResumeTextUnavailableError,
    analyze_user_resume,
)
from backend.app.agents.resume_improver import InvalidResumeImprovementError
from backend.app.agents.structured_llm import (
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)
from backend.app.rag.embeddings import EmbeddingConfigurationError, EmbeddingError
from backend.app.schemas.resume_improvement import ResumeImprovementResponse
from backend.app.services.resume_improvement_service import (
    MissingResumeAnalysisError as MissingImprovementAnalysisError,
    improve_user_resume,
)
from backend.app.models import ResumeAnalysisRecord
from sqlalchemy import select
from backend.app.utils.file_validation import InvalidResumeFile, UnsupportedResumeType


router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeUploadResponse:
    data = await file.read(settings.max_upload_size_bytes + 1)
    if len(data) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="Resume exceeds the configured upload size limit.")
    try:
        resume = create_resume(db, user, file.filename, file.content_type, data)
    except UnsupportedResumeType as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except InvalidResumeFile as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ResumeParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResumeUploadResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        file_type=resume.file_type,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
        file_size_bytes=len(data),
    )


@router.post("/{resume_id}/analyze", response_model=ResumeAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_resume(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeAnalysisResponse:
    try:
        record = await analyze_user_resume(db, user.id, resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    except ResumeTextUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Resume analysis provider timed out.") from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail="Resume analysis provider request failed.") from exc
    except InvalidAIResponseError as exc:
        raise HTTPException(status_code=502, detail="Resume analysis provider returned invalid structured data.") from exc
    return ResumeAnalysisResponse(
        id=record.id,
        resume_id=record.resume_id,
        result=ResumeAnalysis.model_validate(record.result_json),
        model_name=record.model_name,
        created_at=record.created_at,
    )


@router.post("/{resume_id}/improve", response_model=ResumeImprovementResponse)
async def improve_resume(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeImprovementResponse:
    try:
        return await improve_user_resume(db, user.id, resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    except MissingImprovementAnalysisError as exc:
        raise HTTPException(status_code=409, detail="Analyze this resume before requesting improvements.") from exc
    except EmbeddingConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Knowledge embeddings are not configured.") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Resume improvement AI provider is not configured.") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Resume improvement AI provider timed out.") from exc
    except (LLMInvalidResponseError, InvalidResumeImprovementError) as exc:
        raise HTTPException(status_code=502, detail="Resume improvement returned invalid structured data.") from exc
    except (LLMProviderError, EmbeddingError) as exc:
        raise HTTPException(status_code=502, detail="Resume improvement service request failed.") from exc


@router.get("/{resume_id}/analysis", response_model=ResumeAnalysisResponse)
def latest_resume_analysis(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeAnalysisResponse:
    try:
        resume = get_user_resume(db, user.id, resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    record = db.scalar(
        select(ResumeAnalysisRecord).where(ResumeAnalysisRecord.resume_id == resume.id)
        .order_by(ResumeAnalysisRecord.created_at.desc(), ResumeAnalysisRecord.id.desc())
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    return ResumeAnalysisResponse(
        id=record.id,
        resume_id=record.resume_id,
        result=ResumeAnalysis.model_validate(record.result_json),
        model_name=record.model_name,
        created_at=record.created_at,
    )


@router.get("", response_model=list[ResumeResponse])
def list_resumes(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ResumeResponse]:
    return list_user_resumes(db, user.id)


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeResponse:
    try:
        return get_user_resume(db, user.id, resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        delete_user_resume(db, user.id, resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    except InvalidResumeFile as exc:
        raise HTTPException(status_code=500, detail="Stored resume path is invalid") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
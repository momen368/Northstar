from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.agents.structured_llm import (
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)
from backend.app.api.dependencies import get_current_user
from backend.app.database.dependencies import get_db
from backend.app.models import User
from backend.app.schemas.job_matching import MatchRequest, RecommendationResponse
from backend.app.services.job_matching_service import (
    MatchResourceNotFoundError,
    MissingResumeAnalysisError,
    list_resume_recommendations,
    match_resume_to_job,
)


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def response_for(recommendation, job) -> RecommendationResponse:
    details = recommendation.details_json or {}
    created_at = recommendation.created_at.replace(tzinfo=UTC).isoformat()
    return RecommendationResponse(
        id=recommendation.id,
        resume_id=recommendation.resume_id,
        job_id=recommendation.job_id,
        job_title=job.title,
        company=job.company,
        created_at=created_at,
        match_score=recommendation.match_score,
        matched_skills=details.get("matched_skills", []),
        missing_skills=details.get("missing_skills", []),
        explanation=recommendation.explanation,
        recommendation=details.get("recommendation", "Review the missing skills and experience evidence."),
        score_breakdown=details.get("score_breakdown", {}),
    )


@router.post("/match", response_model=RecommendationResponse, status_code=status.HTTP_201_CREATED)
async def match(
    data: MatchRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RecommendationResponse:
    try:
        recommendation, job = await match_resume_to_job(db, user.id, data.resume_id, data.job_id)
        return response_for(recommendation, job)
    except MatchResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingResumeAnalysisError as exc:
        raise HTTPException(status_code=409, detail="Analyze this resume before matching it to a job.") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Job matching AI provider is not configured.") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Job matching AI provider timed out.") from exc
    except LLMInvalidResponseError as exc:
        raise HTTPException(status_code=502, detail="Job matching AI provider returned invalid data.") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail="Job matching AI provider request failed.") from exc


@router.get("/{resume_id}", response_model=list[RecommendationResponse])
def recommendations_for_resume(
    resume_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RecommendationResponse]:
    try:
        return [response_for(recommendation, job)
                for recommendation, job in list_resume_recommendations(db, user.id, resume_id)]
    except MatchResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agents.career_advisor import InvalidCareerAdvisorResponseError
from backend.app.agents.structured_llm import (
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)
from backend.app.api.dependencies import get_current_user
from backend.app.database.dependencies import get_db
from backend.app.models import User
from backend.app.rag.embeddings import EmbeddingConfigurationError, EmbeddingError
from backend.app.schemas.career_advisor import CareerAdvisorResponse
from backend.app.services.career_advisor_service import (
    MissingResumeAnalysisError,
    get_career_advice,
)
from backend.app.services.resume_service import ResumeNotFoundError


router = APIRouter(prefix="/api/career-advisor", tags=["career advisor"])


class CareerAdvisorRequest(BaseModel):
    resume_id: int = Field(gt=0)
    question: str = Field(min_length=3, max_length=5000)


@router.post("", response_model=CareerAdvisorResponse)
async def ask_career_advisor(
    data: CareerAdvisorRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CareerAdvisorResponse:
    try:
        return await get_career_advice(db, user.id, data.resume_id, data.question)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    except MissingResumeAnalysisError as exc:
        raise HTTPException(status_code=409, detail="Analyze this resume before asking for career advice.") from exc
    except EmbeddingConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Career knowledge embeddings are not configured.") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Career advisor AI provider is not configured.") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Career advisor AI provider timed out.") from exc
    except (LLMInvalidResponseError, InvalidCareerAdvisorResponseError) as exc:
        raise HTTPException(status_code=502, detail="Career advisor returned invalid structured data.") from exc
    except (LLMProviderError, EmbeddingError) as exc:
        raise HTTPException(status_code=502, detail="Career advisor service request failed.") from exc
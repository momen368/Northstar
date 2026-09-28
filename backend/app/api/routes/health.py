from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.dependencies import get_db


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "AI Resume Analyzer API"}


@router.get("/health/database", summary="Database health check")
def database_health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}
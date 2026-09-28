from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.database.dependencies import get_db
from backend.app.models import User
from backend.app.schemas.job import JobCreate, JobPage, JobResponse, JobUpdate
from backend.app.services.job_service import (
    JobNotFoundError,
    create_job,
    delete_job,
    get_job,
    list_jobs,
    search_jobs,
    update_job,
)


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description,
        experience_level=job.experience_level,
        skills=[association.skill.name for association in job.job_skills],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create(
    data: JobCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    return to_response(create_job(db, user.id, data))


@router.get("", response_model=JobPage)
def list_all(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobPage:
    jobs, total = list_jobs(db, user.id, limit, offset)
    return JobPage(items=[to_response(job) for job in jobs], total=total, limit=limit, offset=offset)


@router.get("/search", response_model=JobPage)
def search(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    keyword: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=200),
    experience_level: str | None = Query(default=None, max_length=80),
    skill: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobPage:
    jobs, total = search_jobs(db, user.id, keyword, location, experience_level, skill, limit, offset)
    return JobPage(items=[to_response(job) for job in jobs], total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse)
def read(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    try:
        return to_response(get_job(db, user.id, job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@router.put("/{job_id}", response_model=JobResponse)
def replace(
    job_id: int,
    data: JobUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    try:
        return to_response(update_job(db, user.id, job_id, data))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        delete_job(db, user.id, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
from sqlalchemy.orm import Session

from backend.app.models import Job
from backend.app.repositories.job_repository import JobRepository
from backend.app.schemas.job import JobCreate, JobUpdate


class JobNotFoundError(Exception):
    pass


def create_job(db: Session, owner_id: int, data: JobCreate) -> Job:
    return JobRepository(db).create(owner_id, data.model_dump())


def list_jobs(db: Session, owner_id: int, limit: int, offset: int) -> tuple[list[Job], int]:
    return JobRepository(db).list_owned(owner_id, limit, offset)


def search_jobs(
    db: Session,
    owner_id: int,
    keyword: str | None,
    location: str | None,
    experience_level: str | None,
    skill: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    return JobRepository(db).search(owner_id, keyword, location, experience_level, skill, limit, offset)


def get_job(db: Session, owner_id: int, job_id: int) -> Job:
    job = JobRepository(db).get_owned(owner_id, job_id)
    if job is None:
        raise JobNotFoundError
    return job


def update_job(db: Session, owner_id: int, job_id: int, data: JobUpdate) -> Job:
    repository = JobRepository(db)
    job = repository.get_owned(owner_id, job_id)
    if job is None:
        raise JobNotFoundError
    return repository.update(job, data.model_dump())


def delete_job(db: Session, owner_id: int, job_id: int) -> None:
    repository = JobRepository(db)
    job = repository.get_owned(owner_id, job_id)
    if job is None:
        raise JobNotFoundError
    repository.delete(job)
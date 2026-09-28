import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import Resume, User
from backend.app.services.resume_parser import extract_text
from backend.app.utils.file_validation import (
    InvalidResumeFile,
    safe_stored_path,
    validate_resume_file,
)


class ResumeNotFoundError(Exception):
    pass


def create_resume(db: Session, user: User, filename: str | None, content_type: str | None, data: bytes) -> Resume:
    original_filename, file_type, _expected_mime = validate_resume_file(filename, content_type, data)
    stored_filename = f"{uuid.uuid4().hex}.{file_type}"
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_path = safe_stored_path(settings.uploads_dir, stored_filename)
    file_created = False
    try:
        with stored_path.open("xb") as destination:
            file_created = True
            destination.write(data)
        extracted_text = extract_text(stored_path, file_type)
        resume = Resume(
            user_id=user.id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_type=file_type,
            extracted_text=extracted_text,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume
    except Exception:
        db.rollback()
        if file_created:
            stored_path.unlink(missing_ok=True)
        raise


def list_user_resumes(db: Session, user_id: int) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        )
    )


def get_user_resume(db: Session, user_id: int, resume_id: int) -> Resume:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise ResumeNotFoundError
    return resume


def delete_user_resume(db: Session, user_id: int, resume_id: int) -> None:
    resume = get_user_resume(db, user_id, resume_id)
    stored_path = safe_stored_path(settings.uploads_dir, resume.stored_filename)
    db.delete(resume)
    db.commit()
    stored_path.unlink(missing_ok=True)


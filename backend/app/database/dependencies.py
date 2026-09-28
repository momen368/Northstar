from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
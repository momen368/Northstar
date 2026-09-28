from sqlalchemy.orm import Session, sessionmaker

from backend.app.database.engine import engine


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()
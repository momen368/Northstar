from pathlib import Path

from sqlalchemy import inspect

from backend.app.database.base import Base
from backend.app.database.engine import engine


def initialize_database() -> None:
    import backend.app.models  # noqa: F401

    if engine.dialect.name == "sqlite":
        database_path = engine.url.database
        if database_path and database_path != ":memory:":
            Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        inspector = inspect(engine)
        if "jobs" in inspector.get_table_names() and "owner_id" not in {
            column["name"] for column in inspector.get_columns("jobs")
        }:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE jobs ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
                )
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_jobs_owner_id ON jobs (owner_id)")
        inspector = inspect(engine)
        if "recommendations" in inspector.get_table_names() and "details_json" not in {
            column["name"] for column in inspector.get_columns("recommendations")
        }:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN details_json JSON")
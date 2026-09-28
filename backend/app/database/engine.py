from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

from backend.app.core.config import settings


database_url = make_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.get_backend_name() == "sqlite" else {}
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


if database_url.get_backend_name() == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
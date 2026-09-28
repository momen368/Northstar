from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import AuthSession, User
from backend.app.schemas.auth import RegistrationRequest
from backend.app.utils.passwords import hash_password, verify_password


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def register_user(db: Session, data: RegistrationRequest) -> User:
    email = normalize_email(str(data.email))
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise DuplicateEmailError

    user = User(name=data.name, email=email, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEmailError from exc
    db.refresh(user)
    return user


def create_login_session(db: Session, email: str, password: str) -> tuple[User, str, int]:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    raw_token = secrets.token_urlsafe(32)
    ttl_seconds = settings.session_ttl_hours * 60 * 60
    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=ttl_seconds)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.commit()
    return user, raw_token, ttl_seconds


def find_active_session(db: Session, raw_token: str) -> AuthSession | None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if auth_session is None:
        return None
    if auth_session.expires_at <= datetime.now(UTC).replace(tzinfo=None):
        db.delete(auth_session)
        db.commit()
        return None
    return auth_session


def revoke_session(db: Session, auth_session: AuthSession) -> None:
    db.delete(auth_session)
    db.commit()
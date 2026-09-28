from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.database.dependencies import get_db
from backend.app.models import AuthSession, User
from backend.app.services.auth_service import find_active_session


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth_session = find_active_session(db, credentials.credentials)
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_session


def get_current_user(auth_session: Annotated[AuthSession, Depends(get_current_session)]) -> User:
    return auth_session.user
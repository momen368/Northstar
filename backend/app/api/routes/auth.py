from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_session, get_current_user
from backend.app.database.dependencies import get_db
from backend.app.models import AuthSession, User
from backend.app.schemas.auth import LoginRequest, LoginResponse, RegistrationRequest, UserResponse
from backend.app.services.auth_service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    create_login_session,
    register_user,
    revoke_session,
)
from backend.app.core.config import settings


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegistrationRequest, db: Annotated[Session, Depends(get_db)]) -> User:
    try:
        return register_user(db, data)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from exc


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    try:
        user, access_token, expires_in = create_login_session(db, str(data.email), data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return LoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    auth_session: Annotated[AuthSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    revoke_session(db, auth_session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.application.dtos import AuthSessionOut, LoginIn, SetupAdminIn, SetupStatusOut, UserOut
from app.application.use_cases import AuthUseCases
from app.domain.entities import User
from app.domain.exceptions import ForbiddenError, SetupAlreadyCompletedError, UnauthorizedError
from app.infrastructure.config import settings
from app.presentation.dependencies import get_auth_use_cases, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="nequipos_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/status", response_model=SetupStatusOut)
def get_setup_status(use_cases: AuthUseCases = Depends(get_auth_use_cases)) -> SetupStatusOut:
    return SetupStatusOut(requires_initial_setup=use_cases.requires_setup())


@router.post("/setup", response_model=AuthSessionOut, status_code=status.HTTP_201_CREATED)
def setup_initial_admin(
    payload: SetupAdminIn,
    request: Request,
    response: Response,
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> AuthSessionOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        session = use_cases.setup_initial_admin(payload, client_ip)
    except SetupAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    _set_session_cookie(response, session.token)
    return session


@router.post("/login", response_model=AuthSessionOut)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> AuthSessionOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        session = use_cases.login(payload, client_ip)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    _set_session_cookie(response, session.token)
    return session


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("nequipos_token")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user.id or 0,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )

from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.application.use_cases import AdminUseCases, AuthUseCases, DepositUseCases
from app.domain.entities import User, UserRole
from app.domain.exceptions import UnauthorizedError
from app.infrastructure.database import get_db_session
from app.infrastructure.repositories_impl import (
    SqlAlchemyAccountRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyConfigRepository,
    SqlAlchemyTransactionRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security import decode_access_token
from app.infrastructure.socketio_manager import socket_manager
from app.infrastructure.tts_service import HybridSpanishTtsService

_tts_singleton = HybridSpanishTtsService()


def get_auth_use_cases(db: Session = Depends(get_db_session)) -> AuthUseCases:
    return AuthUseCases(
        user_repo=SqlAlchemyUserRepository(db),
        audit_repo=SqlAlchemyAuditRepository(db),
    )


def get_deposit_use_cases(db: Session = Depends(get_db_session)) -> DepositUseCases:
    return DepositUseCases(
        tx_repo=SqlAlchemyTransactionRepository(db),
        account_repo=SqlAlchemyAccountRepository(db),
        config_repo=SqlAlchemyConfigRepository(db),
        tts_service=_tts_singleton,
        ws_manager=socket_manager,
        audit_repo=SqlAlchemyAuditRepository(db),
    )


def get_admin_use_cases(db: Session = Depends(get_db_session)) -> AdminUseCases:
    return AdminUseCases(
        user_repo=SqlAlchemyUserRepository(db),
        account_repo=SqlAlchemyAccountRepository(db),
        config_repo=SqlAlchemyConfigRepository(db),
        audit_repo=SqlAlchemyAuditRepository(db),
        tts_service=_tts_singleton,
        ws_manager=socket_manager,
    )


def get_current_user(
    db: Session = Depends(get_db_session),
    nequipos_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> User:
    raw_token: Optional[str] = nequipos_token
    if not raw_token and authorization and authorization.startswith("Bearer "):
        raw_token = authorization.replace("Bearer ", "", 1).strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida.",
        )

    try:
        claims = decode_access_token(raw_token)
        user_id = int(claims["sub"])
    except (UnauthorizedError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    user = SqlAlchemyUserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente.",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol Administrador para esta operación.",
        )
    return current_user


def require_device_token(
    db: Session = Depends(get_db_session),
    x_api_token: Optional[str] = Header(default=None),
) -> None:
    cfg = SqlAlchemyConfigRepository(db).get_settings()
    if not x_api_token or x_api_token.strip() != cfg.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de dispositivo Android inválido o ausente.",
        )

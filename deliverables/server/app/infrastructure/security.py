from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict

import bcrypt
import jwt

from app.domain.entities import UserRole
from app.domain.exceptions import UnauthorizedError
from app.infrastructure.config import settings


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(user_id: int, username: str, role: UserRole) -> str:
    now = datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Sesión expirada o token JWT inválido.") from exc


def generate_device_api_token() -> str:
    return f"nqp_{secrets.token_urlsafe(32)}"

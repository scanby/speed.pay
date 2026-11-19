from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    CAJERO = "CAJERO"


class DepositSource(str, Enum):
    ANDROID_NOTIFICATION = "ANDROID_NOTIFICATION"
    MANUAL_TEST = "MANUAL_TEST"


@dataclass(frozen=True)
class User:
    id: Optional[int]
    username: str
    full_name: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class NequiAccount:
    id: Optional[int]
    alias: str
    phone_number: str
    device_label: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class DepositTransaction:
    id: Optional[int]
    idempotency_hash: str
    account_id: int
    account_alias: str
    sender_name: str
    amount_cop: Decimal
    amount_words: str
    raw_notification: str
    source: DepositSource
    audio_filename: Optional[str]
    captured_at: datetime
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class AuditLog:
    id: Optional[int]
    actor_username: str
    action: str
    details: str
    ip_address: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ServerSettings:
    api_token: str
    server_port: int
    tts_enabled: bool
    tts_voice: str
    github_repo: str = "tu-usuario/nequipos"
    auto_update_enabled: bool = True
    updated_at: datetime = field(default_factory=datetime.utcnow)

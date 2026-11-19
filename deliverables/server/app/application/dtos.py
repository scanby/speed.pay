from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.entities import DepositSource, UserRole


class SetupStatusOut(BaseModel):
    requires_initial_setup: bool


class SetupAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class AuthSessionOut(BaseModel):
    user: UserOut
    token: str


class CreateCashierIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class NequiAccountIn(BaseModel):
    alias: str = Field(min_length=2, max_length=80)
    phone_number: str = Field(min_length=10, max_length=20)
    device_label: str = Field(min_length=2, max_length=100)


class NequiAccountOut(BaseModel):
    id: int
    alias: str
    phone_number: str
    device_label: str
    is_active: bool
    created_at: datetime


class DepositIngestIn(BaseModel):
    account_alias: str = Field(min_length=1, max_length=80)
    sender_name: str = Field(min_length=1, max_length=160)
    amount_cop: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    raw_notification: str = Field(min_length=1, max_length=1000)
    captured_at: datetime
    source: DepositSource = DepositSource.ANDROID_NOTIFICATION

    @field_validator("sender_name")
    @classmethod
    def sanitize_sender(cls, value: str) -> str:
        return " ".join(value.strip().split())


class DepositOut(BaseModel):
    id: int
    idempotency_hash: str
    account_id: int
    account_alias: str
    sender_name: str
    amount_cop: str
    amount_words: str
    tts_phrase: str
    audio_url: Optional[str]
    source: DepositSource
    captured_at: datetime
    received_at: datetime


class DailyDepositsOut(BaseModel):
    date: date
    count: int
    total_cop: Optional[str] = None
    items: List[DepositOut]


class ServerConfigOut(BaseModel):
    app_version: str
    lan_ip: str
    server_port: int
    api_token: str
    tts_enabled: bool
    tts_voice: str
    github_repo: str
    auto_update_enabled: bool
    active_pos_clients: int
    updated_at: datetime


class UpdateConfigIn(BaseModel):
    tts_enabled: bool
    tts_voice: str = Field(min_length=3, max_length=64)
    server_port: int = Field(ge=1024, le=65535)
    github_repo: str = Field(min_length=3, max_length=160)
    auto_update_enabled: bool = True


class QrConfigOut(BaseModel):
    qr_payload_json: str
    qr_image_base64: str
    lan_ip: str
    server_port: int


class UpdateCheckOut(BaseModel):
    status: str
    current_version: str
    latest_version: str
    update_available: bool
    message: str
    release_notes: str
    server_download_url: Optional[str] = None
    client_download_url: Optional[str] = None
    sha256_sums_url: Optional[str] = None


class UpdateInstallOut(BaseModel):
    status: str
    message: str
    target_version: str


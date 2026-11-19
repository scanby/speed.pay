from __future__ import annotations

import secrets
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.entities import (
    AuditLog,
    DepositSource,
    DepositTransaction,
    NequiAccount,
    ServerSettings,
    User,
    UserRole,
)
from app.domain.repositories import (
    IAccountRepository,
    IAuditRepository,
    IConfigRepository,
    ITransactionRepository,
    IUserRepository,
)
from app.infrastructure.config import settings
from app.infrastructure.database import (
    AuditLogModel,
    DepositTransactionModel,
    NequiAccountModel,
    SystemConfigModel,
    UserModel,
)


class SqlAlchemyUserRepository(IUserRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(
            id=row.id,
            username=row.username,
            full_name=row.full_name,
            password_hash=row.password_hash,
            role=UserRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def count_users(self) -> int:
        return self._db.query(func.count(UserModel.id)).scalar() or 0

    def get_by_username(self, username: str) -> Optional[User]:
        normalized = username.strip().lower()
        row = self._db.query(UserModel).filter(func.lower(UserModel.username) == normalized).first()
        return self._to_entity(row) if row else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        row = self._db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_entity(row) if row else None

    def list_all(self) -> List[User]:
        rows = self._db.query(UserModel).order_by(UserModel.created_at.asc()).all()
        return [self._to_entity(r) for r in rows]

    def create(self, user: User) -> User:
        row = UserModel(
            username=user.username,
            full_name=user.full_name,
            password_hash=user.password_hash,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)

    def set_active(self, user_id: int, is_active: bool) -> Optional[User]:
        row = self._db.query(UserModel).filter(UserModel.id == user_id).first()
        if not row:
            return None
        row.is_active = is_active
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)


class SqlAlchemyAccountRepository(IAccountRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _to_entity(row: NequiAccountModel) -> NequiAccount:
        return NequiAccount(
            id=row.id,
            alias=row.alias,
            phone_number=row.phone_number,
            device_label=row.device_label,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def get_by_id(self, account_id: int) -> Optional[NequiAccount]:
        row = self._db.query(NequiAccountModel).filter(NequiAccountModel.id == account_id).first()
        return self._to_entity(row) if row else None

    def get_by_alias(self, alias: str) -> Optional[NequiAccount]:
        row = self._db.query(NequiAccountModel).filter(NequiAccountModel.alias == alias).first()
        return self._to_entity(row) if row else None

    def list_all(self) -> List[NequiAccount]:
        rows = self._db.query(NequiAccountModel).order_by(NequiAccountModel.created_at.asc()).all()
        return [self._to_entity(r) for r in rows]

    def create(self, account: NequiAccount) -> NequiAccount:
        row = NequiAccountModel(
            alias=account.alias,
            phone_number=account.phone_number,
            device_label=account.device_label,
            is_active=account.is_active,
            created_at=account.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)

    def set_active(self, account_id: int, is_active: bool) -> Optional[NequiAccount]:
        row = self._db.query(NequiAccountModel).filter(NequiAccountModel.id == account_id).first()
        if not row:
            return None
        row.is_active = is_active
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)


class SqlAlchemyTransactionRepository(ITransactionRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _to_entity(row: DepositTransactionModel) -> DepositTransaction:
        return DepositTransaction(
            id=row.id,
            idempotency_hash=row.idempotency_hash,
            account_id=row.account_id,
            account_alias=row.account_alias,
            sender_name=row.sender_name,
            amount_cop=Decimal(row.amount_cop),
            amount_words=row.amount_words,
            raw_notification=row.raw_notification,
            source=DepositSource(row.source),
            audio_filename=row.audio_filename,
            captured_at=row.captured_at,
            received_at=row.received_at,
        )

    def exists_by_hash(self, idempotency_hash: str) -> bool:
        return (
            self._db.query(DepositTransactionModel.id)
            .filter(DepositTransactionModel.idempotency_hash == idempotency_hash)
            .first()
            is not None
        )

    def create(self, tx: DepositTransaction) -> DepositTransaction:
        row = DepositTransactionModel(
            idempotency_hash=tx.idempotency_hash,
            account_id=tx.account_id,
            account_alias=tx.account_alias,
            sender_name=tx.sender_name,
            amount_cop=tx.amount_cop,
            amount_words=tx.amount_words,
            raw_notification=tx.raw_notification,
            source=tx.source.value,
            audio_filename=tx.audio_filename,
            captured_at=tx.captured_at,
            received_at=tx.received_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)

    def list_for_date(self, target_date: date) -> List[DepositTransaction]:
        start_dt = datetime.combine(target_date, time.min)
        end_dt = datetime.combine(target_date, time.max)
        rows = (
            self._db.query(DepositTransactionModel)
            .filter(
                DepositTransactionModel.captured_at >= start_dt,
                DepositTransactionModel.captured_at <= end_dt,
            )
            .order_by(DepositTransactionModel.captured_at.desc())
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def list_by_range(
        self,
        start_date: date,
        end_date: date,
        account_id: Optional[int] = None,
    ) -> List[DepositTransaction]:
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        query = self._db.query(DepositTransactionModel).filter(
            DepositTransactionModel.captured_at >= start_dt,
            DepositTransactionModel.captured_at <= end_dt,
        )
        if account_id is not None:
            query = query.filter(DepositTransactionModel.account_id == account_id)
        rows = query.order_by(DepositTransactionModel.captured_at.desc()).all()
        return [self._to_entity(r) for r in rows]

    def get_daily_summary(self, target_date: date) -> Tuple[int, str]:
        start_dt = datetime.combine(target_date, time.min)
        end_dt = datetime.combine(target_date, time.max)
        count, total = (
            self._db.query(
                func.count(DepositTransactionModel.id),
                func.coalesce(func.sum(DepositTransactionModel.amount_cop), 0),
            )
            .filter(
                DepositTransactionModel.captured_at >= start_dt,
                DepositTransactionModel.captured_at <= end_dt,
            )
            .one()
        )
        return int(count or 0), f"{Decimal(total):.2f}"


class SqlAlchemyAuditRepository(IAuditRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def record(self, log: AuditLog) -> AuditLog:
        row = AuditLogModel(
            actor_username=log.actor_username,
            action=log.action,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return AuditLog(
            id=row.id,
            actor_username=row.actor_username,
            action=row.action,
            details=row.details,
            ip_address=row.ip_address,
            created_at=row.created_at,
        )

    def list_recent(self, limit: int = 100) -> List[AuditLog]:
        rows = (
            self._db.query(AuditLogModel)
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            AuditLog(
                id=r.id,
                actor_username=r.actor_username,
                action=r.action,
                details=r.details,
                ip_address=r.ip_address,
                created_at=r.created_at,
            )
            for r in rows
        ]


class SqlAlchemyConfigRepository(IConfigRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_settings(self) -> ServerSettings:
        row = self._db.query(SystemConfigModel).filter(SystemConfigModel.id == 1).first()
        if not row:
            row = SystemConfigModel(
                id=1,
                api_token=secrets.token_urlsafe(32),
                server_port=settings.SERVER_PORT,
                tts_enabled=True,
                tts_voice=settings.TTS_VOICE,
                github_repo="tu-usuario/nequipos",
                auto_update_enabled=True,
                updated_at=datetime.utcnow(),
            )
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        return ServerSettings(
            api_token=row.api_token,
            server_port=row.server_port,
            tts_enabled=row.tts_enabled,
            tts_voice=row.tts_voice,
            github_repo=row.github_repo,
            auto_update_enabled=row.auto_update_enabled,
            updated_at=row.updated_at,
        )

    def save_settings(self, new_settings: ServerSettings) -> ServerSettings:
        row = self._db.query(SystemConfigModel).filter(SystemConfigModel.id == 1).first()
        if not row:
            row = SystemConfigModel(id=1)
            self._db.add(row)
        row.api_token = new_settings.api_token
        row.server_port = new_settings.server_port
        row.tts_enabled = new_settings.tts_enabled
        row.tts_voice = new_settings.tts_voice
        row.github_repo = new_settings.github_repo
        row.auto_update_enabled = new_settings.auto_update_enabled
        row.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(row)
        return ServerSettings(
            api_token=row.api_token,
            server_port=row.server_port,
            tts_enabled=row.tts_enabled,
            tts_voice=row.tts_voice,
            github_repo=row.github_repo,
            auto_update_enabled=row.auto_update_enabled,
            updated_at=row.updated_at,
        )

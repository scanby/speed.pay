from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional, Tuple

from app.domain.entities import (
    AuditLog,
    DepositTransaction,
    NequiAccount,
    ServerSettings,
    User,
)


class IUserRepository(ABC):
    @abstractmethod
    def count_users(self) -> int: ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]: ...

    @abstractmethod
    def list_all(self) -> List[User]: ...

    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def set_active(self, user_id: int, is_active: bool) -> Optional[User]: ...


class IAccountRepository(ABC):
    @abstractmethod
    def get_by_id(self, account_id: int) -> Optional[NequiAccount]: ...

    @abstractmethod
    def get_by_alias(self, alias: str) -> Optional[NequiAccount]: ...

    @abstractmethod
    def list_all(self) -> List[NequiAccount]: ...

    @abstractmethod
    def create(self, account: NequiAccount) -> NequiAccount: ...

    @abstractmethod
    def set_active(self, account_id: int, is_active: bool) -> Optional[NequiAccount]: ...


class ITransactionRepository(ABC):
    @abstractmethod
    def exists_by_hash(self, idempotency_hash: str) -> bool: ...

    @abstractmethod
    def create(self, tx: DepositTransaction) -> DepositTransaction: ...

    @abstractmethod
    def list_for_date(self, target_date: date) -> List[DepositTransaction]: ...

    @abstractmethod
    def list_by_range(
        self,
        start_date: date,
        end_date: date,
        account_id: Optional[int] = None,
    ) -> List[DepositTransaction]: ...

    @abstractmethod
    def get_daily_summary(self, target_date: date) -> Tuple[int, str]: ...


class IAuditRepository(ABC):
    @abstractmethod
    def record(self, log: AuditLog) -> AuditLog: ...

    @abstractmethod
    def list_recent(self, limit: int = 100) -> List[AuditLog]: ...


class IConfigRepository(ABC):
    @abstractmethod
    def get_settings(self) -> ServerSettings: ...

    @abstractmethod
    def save_settings(self, settings: ServerSettings) -> ServerSettings: ...


class ITtsService(ABC):
    @abstractmethod
    async def synthesize_deposit_phrase(self, phrase: str, tx_hash: str) -> Optional[str]:
        """Generates an audio file (.mp3 or .wav) and returns the relative filename."""
        ...

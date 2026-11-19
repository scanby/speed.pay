from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from app.infrastructure.config import logger, settings


def _ensure_sqlite_dir() -> None:
    if settings.DATABASE_URL.startswith("sqlite:///"):
        db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_wal_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA temp_store=MEMORY;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="CAJERO")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class NequiAccountModel(Base):
    __tablename__ = "nequi_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alias = Column(String(80), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), nullable=False)
    device_label = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    transactions = relationship("DepositTransactionModel", back_populates="account")


class DepositTransactionModel(Base):
    __tablename__ = "deposit_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idempotency_hash = Column(String(64), unique=True, nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("nequi_accounts.id", ondelete="RESTRICT"), nullable=False)
    account_alias = Column(String(80), nullable=False)
    sender_name = Column(String(160), nullable=False)
    amount_cop = Column(Numeric(14, 2), nullable=False)
    amount_words = Column(String(255), nullable=False)
    raw_notification = Column(Text, nullable=False)
    source = Column(String(32), nullable=False, default="ANDROID_NOTIFICATION")
    audio_filename = Column(String(128), nullable=True)
    captured_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    account = relationship("NequiAccountModel", back_populates="transactions")

    __table_args__ = (
        Index("ix_deposit_captured_account", "captured_at", "account_id"),
    )


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_username = Column(String(64), nullable=False, index=True)
    action = Column(String(80), nullable=False)
    details = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class SystemConfigModel(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    api_token = Column(String(128), nullable=False)
    server_port = Column(Integer, nullable=False, default=8000)
    tts_enabled = Column(Boolean, nullable=False, default=True)
    tts_voice = Column(String(64), nullable=False, default="es-CO-SalomeNeural")
    github_repo = Column(String(160), nullable=False, default="tu-usuario/nequipos")
    auto_update_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    # Migración ligera para bases existentes sin perder datos
    with engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(system_config);").fetchall()]
        if "github_repo" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE system_config ADD COLUMN github_repo VARCHAR(160) NOT NULL DEFAULT 'tu-usuario/nequipos';"
            )
        if "auto_update_enabled" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE system_config ADD COLUMN auto_update_enabled BOOLEAN NOT NULL DEFAULT 1;"
            )
    logger.info("Base de datos SQLite inicializada en modo WAL.")


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

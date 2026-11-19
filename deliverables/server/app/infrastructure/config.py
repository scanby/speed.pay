from __future__ import annotations

import logging
import socket
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "NequiPay POS Server"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/nequipos.db"
    LOG_DIR: str = "./logs"
    AUDIO_DIR: str = "./static/audio"
    JWT_SECRET_KEY: str = "nequipos-dev-secret-change-in-production-64-bytes-minimum"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720
    COOKIE_SECURE: bool = False
    IDEMPOTENCY_WINDOW_SECONDS: int = 120
    TTS_VOICE: str = "es-CO-SalomeNeural"
    TTS_TIMEOUT_SECONDS: float = 4.0


settings = Settings()


def detect_lan_ip() -> str:
    """Detecta la IPv4 local activa en la interfaz LAN sin requerir conexión a internet real."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
    except OSError:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


def configure_logging() -> logging.Logger:
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "nequipos_server.log"

    logger = logging.getLogger("nequipos")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB por archivo
            backupCount=10,            # Hasta 50 MB históricos
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


logger = configure_logging()

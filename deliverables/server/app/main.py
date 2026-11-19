from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.infrastructure.config import detect_lan_ip, logger, settings
from app.infrastructure.database import SessionLocal, init_database
from app.infrastructure.repositories_impl import SqlAlchemyConfigRepository
from app.infrastructure.socketio_manager import socket_manager
from app.presentation.routes import admin_routes, auth_routes, deposit_routes


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    with SessionLocal() as db:
        SqlAlchemyConfigRepository(db).get_settings()
    Path(settings.AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    lan_ip = detect_lan_ip()
    logger.info(
        "NequiPay POS Central iniciado en http://%s:%s (Modo WAL activo)",
        lan_ip,
        settings.SERVER_PORT,
    )
    yield
    logger.info("Deteniendo servidor NequiPay POS...")


fastapi_app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(auth_routes.router)
fastapi_app.include_router(deposit_routes.router)
fastapi_app.include_router(admin_routes.router)

Path(settings.AUDIO_DIR).mkdir(parents=True, exist_ok=True)
fastapi_app.mount("/static/audio", StaticFiles(directory=settings.AUDIO_DIR), name="audio")

# Sirve el Frontend Web POS compatible con Windows 7 (ES5/ES6), tanto en dev como dentro de PyInstaller .exe
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    CLIENT_WEB_DIR = Path(sys._MEIPASS) / "client_win7" / "web_pos"
else:
    CLIENT_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "client_win7" / "web_pos"

if CLIENT_WEB_DIR.exists():
    fastapi_app.mount("/pos", StaticFiles(directory=str(CLIENT_WEB_DIR), html=True), name="pos_web")


@fastapi_app.get("/api/health")
def health_check() -> dict:
    return {
        "status": "online",
        "lan_ip": detect_lan_ip(),
        "active_pos_clients": socket_manager.get_active_client_count(),
    }


@fastapi_app.get("/")
def root_redirect():
    index_file = CLIENT_WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"service": settings.APP_NAME, "status": "running"}


# Monta Socket.IO envolviendo FastAPI en ASGI
app = socketio.ASGIApp(socket_manager.sio, other_asgi_app=fastapi_app)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        log_level="info",
    )

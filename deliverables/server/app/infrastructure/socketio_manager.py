from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import socketio

from app.infrastructure.config import logger


class SocketIOManager:
    def __init__(self) -> None:
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",
            ping_interval=5,
            ping_timeout=10,
        )
        self._connected_clients: Dict[str, Dict[str, Any]] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.sio.event
        async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
            client_ip = environ.get("REMOTE_ADDR", "unknown")
            agent_type = (auth or {}).get("agent", "web_browser")
            self._connected_clients[sid] = {
                "ip": client_ip,
                "agent": agent_type,
                "connected_at": datetime.utcnow().isoformat(),
            }
            await self.sio.enter_room(sid, "pos_monitors")
            logger.info("Cliente POS conectado: sid=%s ip=%s agent=%s", sid, client_ip, agent_type)

        @self.sio.event
        async def disconnect(sid: str) -> None:
            info = self._connected_clients.pop(sid, None)
            logger.warning("Cliente POS desconectado: sid=%s info=%s", sid, info)

        @self.sio.on("heartbeat_ping")
        async def handle_heartbeat(sid: str, data: dict | None = None) -> dict:
            return {
                "status": "ok",
                "server_time": datetime.utcnow().isoformat(),
                "active_clients": len(self._connected_clients),
            }

    async def broadcast_deposit(self, payload: Dict[str, Any]) -> None:
        await self.sio.emit("new_deposit", payload, room="pos_monitors")
        logger.info(
            "Evento new_deposit emitido a %d clientes POS (tx_id=%s, monto=%s)",
            len(self._connected_clients),
            payload.get("id"),
            payload.get("amount_cop"),
        )

    def get_active_client_count(self) -> int:
        return len(self._connected_clients)


socket_manager = SocketIOManager()

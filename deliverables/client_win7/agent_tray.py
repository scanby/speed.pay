# -*- coding: utf-8 -*-
"""
Agente Nativo POS para Windows 7 / 10 / 11 (Python 3.8 compatible).
- Incluye Panel de Configuración local (Tkinter) para definir la IP estática del PC Servidor,
  puerto, nombre de caja y volumen sin recompilar ni editar accesos directos.
- Mantiene conexión Socket.IO persistente en segundo plano con reconexión exponencial.
- Descarga el audio WAV/MP3 generado por el servidor y lo reproduce con pygame.mixer,
  evitando cualquier bloqueo de autoplay del navegador en cajas registradoras.
- Muestra icono en bandeja del sistema (Verde: Conectado / Rojo: Desconectado).
"""
import argparse
import logging
import os
import subprocess
import tempfile
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler

import pygame
import pystray
import requests
import socketio
from PIL import Image, ImageDraw

from client_config import (
    build_server_url,
    config_exists,
    load_client_config,
    save_client_config,
)
from client_updater import (
    apply_unattended_client_update,
    check_client_update,
    get_client_version,
)
from config_window import open_config_dialog

LOG_DIR = os.path.join(os.path.expanduser("~"), ".nequipos_client", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("nequipos_win7_agent")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "client_agent.log"),
    maxBytes=2 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(handler)


def create_status_icon(color_hex):
    image = Image.new("RGB", (64, 64), (15, 23, 42))
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, 54, 54), fill=color_hex)
    return image


class PosTrayAgent(object):
    def __init__(self, initial_config):
        self.config = initial_config
        self.server_url = build_server_url(initial_config)
        self.running = True
        self.connected = False
        self.reconnect_requested = False
        self.audio_lock = threading.Lock()
        self.tray_icon = None

        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1,
            reconnection_delay_max=30,
            logger=False,
        )
        self._register_socket_events()

    def _register_socket_events(self):
        @self.sio.event
        def connect():
            self.connected = True
            logger.info("Conectado al servidor POS: %s", self.server_url)
            self._update_tray_visual()

        @self.sio.event
        def disconnect():
            self.connected = False
            logger.warning("Desconectado del servidor POS. Reconexión automática activa.")
            self._update_tray_visual()

        @self.sio.on("new_deposit")
        def on_new_deposit(payload):
            logger.info(
                "Depósito recibido: $%s de %s",
                payload.get("amount_cop"),
                payload.get("sender_name"),
            )
            audio_rel = payload.get("audio_url")
            if audio_rel:
                threading.Thread(
                    target=self._download_and_play,
                    args=(self.server_url + audio_rel,),
                    daemon=True,
                ).start()

    def _update_tray_visual(self):
        if self.tray_icon is not None:
            color = "#16A34A" if self.connected else "#DC2626"
            status_text = "En línea" if self.connected else "Desconectado"
            label = self.config.get("pos_label", "Caja POS")
            self.tray_icon.icon = create_status_icon(color)
            self.tray_icon.title = "NequiPay POS · {0} ({1})".format(label, status_text)

    def _download_and_play(self, full_audio_url):
        with self.audio_lock:
            tmp_path = None
            try:
                resp = requests.get(full_audio_url, timeout=6)
                resp.raise_for_status()
                ext = ".wav" if full_audio_url.endswith(".wav") else ".mp3"
                fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="nequi_tts_")
                with os.fdopen(fd, "wb") as f:
                    f.write(resp.content)

                volume = max(0.0, min(1.0, float(self.config.get("audio_volume", 100)) / 100.0))
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            except Exception as exc:
                logger.error("Error reproduciendo audio TTS %s: %s", full_audio_url, exc)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def open_pos_kiosk(self, _icon=None, _item=None):
        target = self.server_url + "/pos/"
        if not self.config.get("kiosk_mode", True):
            webbrowser.open(target)
            return

        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for exe in chrome_paths:
            if os.path.exists(exe):
                subprocess.Popen([exe, "--app=" + target, "--window-size=1280,800"])
                return
        webbrowser.open(target)

    def open_configuration_panel(self, _icon=None, _item=None):
        def _run_ui():
            def on_saved(new_cfg):
                self.config = new_cfg
                new_url = build_server_url(new_cfg)
                if new_url != self.server_url:
                    self.server_url = new_url
                    self.reconnect_requested = True
                    try:
                        if self.sio.connected:
                            self.sio.disconnect()
                    except Exception:
                        pass
                self._update_tray_visual()
                logger.info("Configuración actualizada en vivo -> %s", self.server_url)

            open_config_dialog(on_save_callback=on_saved)

        threading.Thread(target=_run_ui, daemon=True).start()

    def _socket_loop(self):
        backoff = 1
        while self.running:
            if self.reconnect_requested:
                self.reconnect_requested = False
                backoff = 1

            if not self.sio.connected:
                try:
                    self.sio.connect(
                        self.server_url,
                        auth={
                            "agent": "win7_python_tray",
                            "pos_label": self.config.get("pos_label", "Caja"),
                        },
                        transports=["websocket", "polling"],
                    )
                    backoff = 1
                except Exception as exc:
                    logger.warning(
                        "Fallo conexión Socket.IO a %s (%s). Reintento en %ds",
                        self.server_url,
                        exc,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
            else:
                try:
                    self.sio.emit("heartbeat_ping", {"ts": time.time()})
                except Exception:
                    pass
            time.sleep(5)

    def _auto_update_loop(self):
        time.sleep(45)
        while self.running:
            try:
                if self.config.get("auto_update_enabled", True):
                    res = check_client_update(self.config.get("github_repo", ""))
                    if res["status"] == "update_available" and res.get("download_url"):
                        logger.info(
                            "Actualización desatendida detectada: v%s -> v%s",
                            res["current_version"],
                            res["latest_version"],
                        )
                        ok, msg = apply_unattended_client_update(
                            res["download_url"],
                            res.get("sha256_sums_url"),
                        )
                        logger.info("Resultado actualización desatendida: %s (%s)", ok, msg)
                        if ok:
                            os._exit(0)
            except Exception as exc:
                logger.warning("Fallo verificando actualización automática: %s", exc)
            time.sleep(6 * 3600)

    def stop(self, _icon=None, _item=None):
        self.running = False
        try:
            self.sio.disconnect()
        except Exception:
            pass
        if self.tray_icon is not None:
            self.tray_icon.stop()

    def run(self):
        worker = threading.Thread(target=self._socket_loop, daemon=True)
        worker.start()
        updater_worker = threading.Thread(target=self._auto_update_loop, daemon=True)
        updater_worker.start()

        ver_label = "Configurar Servidor y Actualizaciones (v{0})".format(get_client_version())
        menu = pystray.Menu(
            pystray.MenuItem("Abrir Monitor POS", self.open_pos_kiosk, default=True),
            pystray.MenuItem(ver_label, self.open_configuration_panel),
            pystray.MenuItem("Salir", self.stop),
        )
        self.tray_icon = pystray.Icon(
            "nequipos_client",
            create_status_icon("#DC2626"),
            "NequiPay POS (Conectando...)",
            menu,
        )
        if self.config.get("auto_open_browser", True):
            self.open_pos_kiosk()
        self.tray_icon.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente POS NequiPay para Windows 7/10/11")
    parser.add_argument("--server-ip", default=None, help="IP estática del Servidor Central")
    parser.add_argument("--port", type=int, default=None, help="Puerto del Servidor Central")
    parser.add_argument("--configure", action="store_true", help="Abrir panel de configuración al iniciar")
    args = parser.parse_args()

    if args.configure or not config_exists():
        open_config_dialog()

    cfg = load_client_config()
    if args.server_ip or args.port:
        if args.server_ip:
            cfg["server_ip"] = args.server_ip
        if args.port:
            cfg["server_port"] = args.port
        cfg = save_client_config(cfg)

    agent = PosTrayAgent(initial_config=cfg)
    agent.run()

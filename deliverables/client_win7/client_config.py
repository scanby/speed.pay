# -*- coding: utf-8 -*-
"""
Persistencia de configuración local para el Agente Cliente POS (Windows 7/10/11).
Almacena la IP estática del PC Servidor, puerto, modo kiosco y volumen en JSON local.
"""
import json
import os
import time
import requests

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".nequipos_client")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "server_ip": "192.168.1.50",
    "server_port": 8000,
    "kiosk_mode": True,
    "auto_open_browser": True,
    "audio_volume": 100,
    "pos_label": "Caja 1",
}


def config_exists():
    return os.path.exists(CONFIG_PATH)


def load_client_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_client_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    clean = {
        "server_ip": str(cfg.get("server_ip", "192.168.1.50")).strip(),
        "server_port": int(cfg.get("server_port", 8000)),
        "kiosk_mode": bool(cfg.get("kiosk_mode", True)),
        "auto_open_browser": bool(cfg.get("auto_open_browser", True)),
        "audio_volume": max(0, min(100, int(cfg.get("audio_volume", 100)))),
        "pos_label": str(cfg.get("pos_label", "Caja 1")).strip() or "Caja 1",
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


def build_server_url(cfg):
    return "http://{0}:{1}".format(cfg["server_ip"], cfg["server_port"])


def test_server_connection(server_ip, server_port):
    url = "http://{0}:{1}/api/health".format(str(server_ip).strip(), int(server_port))
    started = time.time()
    try:
        resp = requests.get(url, timeout=3.5)
        latency_ms = int((time.time() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            return True, "Conexión exitosa ({0} ms) · IP Servidor: {1}".format(
                latency_ms, data.get("lan_ip", server_ip)
            )
        return False, "Servidor respondió HTTP {0}".format(resp.status_code)
    except Exception as exc:
        return False, "Sin respuesta del servidor ({0})".format(exc)

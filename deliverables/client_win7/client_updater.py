# -*- coding: utf-8 -*-
"""
Actualizador Desatendido para Agente Cliente POS (Windows 7 SP1 / 10 / 11 - Python 3.8).
- Compara la versión local instalada contra la última release de GitHub.
- Verifica integridad SHA-256 con SHA256SUMS.txt antes de reemplazar el ejecutable.
- Ejecuta reemplazo atómico vía script .cmd desatendido (sin intervención del usuario) y reinicia.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import requests

DEFAULT_VERSION = "1.0.0"
CLIENT_ASSET_NAME = "NequiPayPOS_Client_Win7.exe"


def get_client_version():
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "VERSION"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION"))

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    val = f.read().strip().lstrip("vV")
                if val:
                    return val
            except Exception:
                pass
    return DEFAULT_VERSION


def parse_semver(version_str):
    cleaned = str(version_str or "").strip().lstrip("vV")
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", cleaned)
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def check_client_update(github_repo):
    current_ver = get_client_version()
    repo = str(github_repo or "").strip().strip("/")
    if not repo or "/" not in repo:
        return {
            "status": "error",
            "current_version": current_ver,
            "latest_version": current_ver,
            "update_available": False,
            "message": "Repositorio GitHub no configurado (ej. usuario/repositorio).",
            "download_url": None,
            "sha256_sums_url": None,
        }

    api_url = "https://api.github.com/repos/{0}/releases/latest".format(repo)
    try:
        resp = requests.get(
            api_url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "NequiPayPOS-Win7-Updater"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {
            "status": "error",
            "current_version": current_ver,
            "latest_version": current_ver,
            "update_available": False,
            "message": "No se pudo consultar el repositorio ({0}).".format(exc),
            "download_url": None,
            "sha256_sums_url": None,
        }

    latest_ver = str(data.get("tag_name") or current_ver).lstrip("vV")
    download_url = None
    sums_url = None
    for asset in data.get("assets") or []:
        name = asset.get("name", "")
        if name == CLIENT_ASSET_NAME:
            download_url = asset.get("browser_download_url")
        elif name == "SHA256SUMS.txt":
            sums_url = asset.get("browser_download_url")

    if parse_semver(latest_ver) > parse_semver(current_ver):
        return {
            "status": "update_available",
            "current_version": current_ver,
            "latest_version": latest_ver,
            "update_available": True,
            "message": "Nueva versión v{0} disponible (tienes v{1}). Se recomienda actualizar.".format(
                latest_ver, current_ver
            ),
            "download_url": download_url,
            "sha256_sums_url": sums_url,
        }

    return {
        "status": "up_to_date",
        "current_version": current_ver,
        "latest_version": latest_ver,
        "update_available": False,
        "message": "Tienes la versión más reciente instalada (v{0}).".format(current_ver),
        "download_url": download_url,
        "sha256_sums_url": sums_url,
    }


def apply_unattended_client_update(download_url, sha256_sums_url=None):
    if not getattr(sys, "frozen", False):
        return False, "La actualización binaria desatendida requiere ejecutar el cliente compilado (.exe)."

    exe_path = os.path.abspath(sys.executable)
    updates_dir = os.path.join(os.path.dirname(exe_path), "updates")
    os.makedirs(updates_dir, exist_ok=True)
    staged_exe = os.path.join(updates_dir, "NequiPayPOS_Client_Win7.new.exe")

    try:
        resp = requests.get(download_url, stream=True, timeout=60)
        resp.raise_for_status()
        hasher = hashlib.sha256()
        with open(staged_exe, "wb") as out_f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    out_f.write(chunk)
                    hasher.update(chunk)
        computed_hash = hasher.hexdigest().lower()

        if sha256_sums_url:
            sums_resp = requests.get(sha256_sums_url, timeout=15)
            sums_resp.raise_for_status()
            if computed_hash not in sums_resp.text.lower():
                if os.path.exists(staged_exe):
                    os.remove(staged_exe)
                return False, "Fallo de verificación SHA-256. Actualización cancelada."

        pid = os.getpid()
        backup_exe = exe_path + ".bak"
        cmd_path = os.path.join(tempfile.gettempdir(), "nequipos_win7_update_{0}.cmd".format(pid))

        # Compatible con Windows 7 SP1 (usa ping -n 2 como espera confiable sin depender de timeout)
        script = (
            "@echo off\r\n"
            "setlocal\r\n"
            ":waitloop\r\n"
            'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\r\n'
            'if "%ERRORLEVEL%"=="0" (\r\n'
            "    ping -n 2 127.0.0.1 >NUL\r\n"
            "    goto waitloop\r\n"
            ")\r\n"
            'copy /Y "{exe}" "{bak}" >NUL 2>&1\r\n'
            'move /Y "{staged}" "{exe}" >NUL\r\n'
            'if exist "{exe}" (\r\n'
            '    start "" "{exe}"\r\n'
            ")\r\n"
            'del "%~f0"\r\n'
        ).format(pid=pid, exe=exe_path, bak=backup_exe, staged=staged_exe)

        with open(cmd_path, "w", encoding="utf-8") as f:
            f.write(script)

        creation_flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        subprocess.Popen(["cmd.exe", "/c", cmd_path], creationflags=creation_flags, close_fds=True)
        return True, "Actualización descargada y verificada. Reiniciando cliente..."
    except Exception as exc:
        return False, "Error aplicando actualización: {0}".format(exc)

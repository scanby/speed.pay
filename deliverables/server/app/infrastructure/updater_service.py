from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import httpx

from app.infrastructure.config import RUNTIME_DIR, logger

DEFAULT_VERSION = "1.0.0"
SERVER_ASSET_NAME = "NequiPayPOS_Server_Win10_11.exe"
CLIENT_ASSET_NAME = "NequiPayPOS_Client_Win7.exe"


def get_installed_version() -> str:
    """Lee la versión embebida en PyInstaller (_MEIPASS/VERSION) o local VERSION."""
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "VERSION")
    candidates.append(RUNTIME_DIR / "VERSION")
    candidates.append(Path(__file__).resolve().parent.parent.parent / "VERSION")

    for path in candidates:
        if path.exists():
            val = path.read_text(encoding="utf-8").strip().lstrip("vV")
            if val:
                return val
    return DEFAULT_VERSION


def parse_semver(version_str: str) -> Tuple[int, int, int]:
    cleaned = version_str.strip().lstrip("vV")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", cleaned)
    if not match:
        return (0, 0, 0)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


@dataclass(frozen=True)
class ReleaseCheckResult:
    status: str  # "up_to_date" | "update_available" | "error"
    current_version: str
    latest_version: str
    update_available: bool
    message: str
    release_notes: str
    server_download_url: Optional[str]
    client_download_url: Optional[str]
    sha256_sums_url: Optional[str]


class UnattendedUpdaterService:
    def __init__(self, timeout_sec: float = 10.0) -> None:
        self._timeout = timeout_sec

    async def check_for_updates(self, github_repo: str) -> ReleaseCheckResult:
        current_ver = get_installed_version()
        repo = github_repo.strip().strip("/")
        if not repo or "/" not in repo:
            return ReleaseCheckResult(
                status="error",
                current_version=current_ver,
                latest_version=current_ver,
                update_available=False,
                message="Repositorio GitHub no configurado (formato esperado: usuario/repositorio).",
                release_notes="",
                server_download_url=None,
                client_download_url=None,
                sha256_sums_url=None,
            )

        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(
                    api_url,
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "NequiPayPOS-Updater"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Error consultando releases de %s: %s", repo, exc)
            return ReleaseCheckResult(
                status="error",
                current_version=current_ver,
                latest_version=current_ver,
                update_available=False,
                message=f"No se pudo consultar el repositorio ({exc}).",
                release_notes="",
                server_download_url=None,
                client_download_url=None,
                sha256_sums_url=None,
            )

        tag_name = str(data.get("tag_name") or current_ver).lstrip("vV")
        release_notes = str(data.get("body") or "")
        assets = data.get("assets") or []

        server_url: Optional[str] = None
        client_url: Optional[str] = None
        sums_url: Optional[str] = None

        for asset in assets:
            name = asset.get("name", "")
            dl = asset.get("browser_download_url")
            if name == SERVER_ASSET_NAME:
                server_url = dl
            elif name == CLIENT_ASSET_NAME:
                client_url = dl
            elif name == "SHA256SUMS.txt":
                sums_url = dl

        is_newer = parse_semver(tag_name) > parse_semver(current_ver)
        if is_newer:
            return ReleaseCheckResult(
                status="update_available",
                current_version=current_ver,
                latest_version=tag_name,
                update_available=True,
                message=f"Nueva versión v{tag_name} disponible (instalada: v{current_ver}). Se recomienda actualizar.",
                release_notes=release_notes,
                server_download_url=server_url,
                client_download_url=client_url,
                sha256_sums_url=sums_url,
            )

        return ReleaseCheckResult(
            status="up_to_date",
            current_version=current_ver,
            latest_version=tag_name,
            update_available=False,
            message=f"Tienes la versión más reciente instalada (v{current_ver}).",
            release_notes=release_notes,
            server_download_url=server_url,
            client_download_url=client_url,
            sha256_sums_url=sums_url,
        )

    async def download_and_schedule_unattended_install(
        self,
        download_url: str,
        sha256_sums_url: Optional[str] = None,
    ) -> str:
        if not getattr(sys, "frozen", False):
            raise RuntimeError(
                "El reemplazo binario desatendido solo aplica cuando el servidor corre compilado como .exe."
            )

        exe_path = Path(sys.executable).resolve()
        updates_dir = exe_path.parent / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        staged_exe = updates_dir / f"{exe_path.stem}.new.exe"

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", download_url) as stream:
                stream.raise_for_status()
                hasher = hashlib.sha256()
                with open(staged_exe, "wb") as out_f:
                    async for chunk in stream.aiter_bytes(chunk_size=65536):
                        out_f.write(chunk)
                        hasher.update(chunk)
                computed_sha256 = hasher.hexdigest().lower()

            if sha256_sums_url:
                sums_resp = await client.get(sha256_sums_url)
                sums_resp.raise_for_status()
                sums_text = sums_resp.text.lower()
                if computed_sha256 not in sums_text:
                    staged_exe.unlink(missing_ok=True)
                    raise ValueError(
                        "Fallo de integridad SHA-256 al verificar el ejecutable descargado. Actualización abortada."
                    )

        pid = os.getpid()
        backup_exe = exe_path.with_suffix(".exe.bak")
        cmd_path = Path(tempfile.gettempdir()) / f"nequipos_srv_update_{pid}.cmd"

        # Script desatendido compatible con Windows 10/11 (incluyendo reinicio silencioso)
        script_content = f"""@echo off
setlocal
:waitloop
tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >NUL
    goto waitloop
)
copy /Y "{exe_path}" "{backup_exe}" >NUL 2>&1
move /Y "{staged_exe}" "{exe_path}" >NUL
if exist "{exe_path}" (
    start "" "{exe_path}"
)
del "%~f0"
"""
        cmd_path.write_text(script_content, encoding="utf-8")

        creation_flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        subprocess.Popen(
            ["cmd.exe", "/c", str(cmd_path)],
            creationflags=creation_flags,
            close_fds=True,
        )
        logger.info("Actualización desatendida programada (PID=%d -> %s).", pid, exe_path)
        return str(staged_exe)

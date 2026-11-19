import asyncio
import base64
import csv
import io
import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

import qrcode

from app.application.dtos import (
    AuthSessionOut,
    CreateCashierIn,
    DailyDepositsOut,
    DepositIngestIn,
    DepositOut,
    LoginIn,
    NequiAccountIn,
    NequiAccountOut,
    QrConfigOut,
    ServerConfigOut,
    SetupAdminIn,
    UpdateCheckOut,
    UpdateConfigIn,
    UpdateInstallOut,
    UserOut,
)
from app.domain.entities import (
    AuditLog,
    DepositTransaction,
    NequiAccount,
    ServerSettings,
    User,
    UserRole,
)
from app.domain.exceptions import (
    DuplicateTransactionError,
    ForbiddenError,
    ResourceNotFoundError,
    SetupAlreadyCompletedError,
    UnauthorizedError,
)
from app.domain.repositories import (
    IAccountRepository,
    IAuditRepository,
    IConfigRepository,
    ITransactionRepository,
    ITtsService,
    IUserRepository,
)
from app.domain.services import (
    build_tts_phrase,
    compute_idempotency_hash,
    monto_a_letras,
)
from app.infrastructure.config import detect_lan_ip, logger, settings
from app.infrastructure.security import (
    create_access_token,
    generate_device_api_token,
    hash_password,
    verify_password,
)
from app.infrastructure.socketio_manager import SocketIOManager
from app.infrastructure.updater_service import (
    UnattendedUpdaterService,
    get_installed_version,
)


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id or 0,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _to_deposit_out(tx: DepositTransaction) -> DepositOut:
    audio_url = f"/static/audio/{tx.audio_filename}" if tx.audio_filename else None
    return DepositOut(
        id=tx.id or 0,
        idempotency_hash=tx.idempotency_hash,
        account_id=tx.account_id,
        account_alias=tx.account_alias,
        sender_name=tx.sender_name,
        amount_cop=f"{tx.amount_cop:.2f}",
        amount_words=tx.amount_words,
        tts_phrase=f"Pago por el valor de {tx.amount_words}",
        audio_url=audio_url,
        source=tx.source,
        captured_at=tx.captured_at,
        received_at=tx.received_at,
    )


class AuthUseCases:
    def __init__(self, user_repo: IUserRepository, audit_repo: IAuditRepository) -> None:
        self._users = user_repo
        self._audit = audit_repo

    def requires_setup(self) -> bool:
        return self._users.count_users() == 0

    def setup_initial_admin(self, payload: SetupAdminIn, client_ip: str) -> AuthSessionOut:
        if self._users.count_users() > 0:
            raise SetupAlreadyCompletedError("El administrador inicial ya fue configurado.")

        created = self._users.create(
            User(
                id=None,
                username=payload.username.strip(),
                full_name=payload.full_name.strip(),
                password_hash=hash_password(payload.password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=created.username,
                action="INITIAL_ADMIN_SETUP",
                details="Creación inicial de cuenta Administrador.",
                ip_address=client_ip,
            )
        )
        token = create_access_token(created.id or 0, created.username, created.role)
        return AuthSessionOut(user=_to_user_out(created), token=token)

    def login(self, payload: LoginIn, client_ip: str) -> AuthSessionOut:
        user = self._users.get_by_username(payload.username.strip())
        if not user or not verify_password(payload.password, user.password_hash):
            logger.warning("Intento de acceso fallido para usuario '%s' desde %s", payload.username, client_ip)
            raise UnauthorizedError("Credenciales inválidas.")
        if not user.is_active:
            raise ForbiddenError("Usuario deshabilitado por el Administrador.")

        self._audit.record(
            AuditLog(
                id=None,
                actor_username=user.username,
                action="USER_LOGIN",
                details=f"Inicio de sesión rol {user.role.value}.",
                ip_address=client_ip,
            )
        )
        token = create_access_token(user.id or 0, user.username, user.role)
        return AuthSessionOut(user=_to_user_out(user), token=token)


class DepositUseCases:
    def __init__(
        self,
        tx_repo: ITransactionRepository,
        account_repo: IAccountRepository,
        config_repo: IConfigRepository,
        tts_service: ITtsService,
        ws_manager: SocketIOManager,
        audit_repo: IAuditRepository,
    ) -> None:
        self._tx = tx_repo
        self._accounts = account_repo
        self._config = config_repo
        self._tts = tts_service
        self._ws = ws_manager
        self._audit = audit_repo

    async def ingest_deposit(self, payload: DepositIngestIn, client_ip: str) -> DepositOut:
        account = self._accounts.get_by_alias(payload.account_alias.strip())
        if not account:
            # Auto-registra una cuenta Nequi si proviene de un dispositivo autorizado con nuevo alias
            account = self._accounts.create(
                NequiAccount(
                    id=None,
                    alias=payload.account_alias.strip(),
                    phone_number="No especificado",
                    device_label=f"Android LAN ({client_ip})",
                    is_active=True,
                )
            )
            logger.info("Cuenta Nequi auto-vinculada por alias: %s", account.alias)

        if not account.is_active:
            raise ForbiddenError(f"La cuenta Nequi '{account.alias}' se encuentra inactiva.")

        tx_hash = compute_idempotency_hash(
            account_id=account.id or 0,
            sender_name=payload.sender_name,
            amount_cop=payload.amount_cop,
            captured_at=payload.captured_at,
            window_seconds=settings.IDEMPOTENCY_WINDOW_SECONDS,
        )

        if self._tx.exists_by_hash(tx_hash):
            logger.info("Depósito duplicado bloqueado por idempotencia SHA-256: %s", tx_hash[:16])
            raise DuplicateTransactionError(tx_hash)

        amount_words = monto_a_letras(payload.amount_cop)
        tts_phrase = build_tts_phrase(payload.amount_cop)
        sys_cfg = self._config.get_settings()

        audio_filename: Optional[str] = None
        if sys_cfg.tts_enabled:
            audio_filename = await self._tts.synthesize_deposit_phrase(tts_phrase, tx_hash)

        saved = self._tx.create(
            DepositTransaction(
                id=None,
                idempotency_hash=tx_hash,
                account_id=account.id or 0,
                account_alias=account.alias,
                sender_name=payload.sender_name,
                amount_cop=payload.amount_cop,
                amount_words=amount_words,
                raw_notification=payload.raw_notification,
                source=payload.source,
                audio_filename=audio_filename,
                captured_at=payload.captured_at,
                received_at=datetime.utcnow(),
            )
        )

        dto = _to_deposit_out(saved)
        await self._ws.broadcast_deposit(dto.model_dump(mode="json"))
        self._audit.record(
            AuditLog(
                id=None,
                actor_username="ANDROID_AGENT",
                action="DEPOSIT_INGESTED",
                details=f"Alias={account.alias} Monto={dto.amount_cop} Remitente={dto.sender_name}",
                ip_address=client_ip,
            )
        )
        return dto

    def get_today_for_role(self, role: UserRole) -> DailyDepositsOut:
        today = date.today()
        items = [_to_deposit_out(tx) for tx in self._tx.list_for_date(today)]
        if role == UserRole.CAJERO:
            # Cajero (Invitado) consulta únicamente los depósitos del día sin totales consolidados ni históricos
            return DailyDepositsOut(date=today, count=len(items), total_cop=None, items=items)

        count, total_cop = self._tx.get_daily_summary(today)
        return DailyDepositsOut(date=today, count=count, total_cop=total_cop, items=items)

    def get_history(
        self,
        start_date: date,
        end_date: date,
        account_id: Optional[int] = None,
    ) -> List[DepositOut]:
        rows = self._tx.list_by_range(start_date, end_date, account_id)
        return [_to_deposit_out(tx) for tx in rows]

    def export_csv(
        self,
        start_date: date,
        end_date: date,
        account_id: Optional[int] = None,
    ) -> str:
        rows = self._tx.list_by_range(start_date, end_date, account_id)
        buffer = io.StringIO()
        # BOM UTF-8 para compatibilidad directa al abrir en Excel de Windows 7/10
        buffer.write("\ufeff")
        writer = csv.writer(buffer)
        writer.writerow([
            "ID",
            "Fecha Captura",
            "Fecha Recepción",
            "Cuenta Nequi",
            "Remitente",
            "Monto COP",
            "Monto en Letras",
            "Origen",
            "Hash Idempotencia SHA-256",
        ])
        for tx in rows:
            writer.writerow([
                tx.id,
                tx.captured_at.isoformat(),
                tx.received_at.isoformat(),
                tx.account_alias,
                tx.sender_name,
                f"{tx.amount_cop:.2f}",
                tx.amount_words,
                tx.source.value,
                tx.idempotency_hash,
            ])
        return buffer.getvalue()


class AdminUseCases:
    def __init__(
        self,
        user_repo: IUserRepository,
        account_repo: IAccountRepository,
        config_repo: IConfigRepository,
        audit_repo: IAuditRepository,
        tts_service: ITtsService,
        ws_manager: SocketIOManager,
    ) -> None:
        self._users = user_repo
        self._accounts = account_repo
        self._config = config_repo
        self._audit = audit_repo
        self._tts = tts_service
        self._ws = ws_manager

    def list_users(self) -> List[UserOut]:
        return [_to_user_out(u) for u in self._users.list_all()]

    def create_cashier(self, payload: CreateCashierIn, actor: str, client_ip: str) -> UserOut:
        if self._users.get_by_username(payload.username.strip()):
            raise ForbiddenError("El nombre de usuario ya existe.")
        created = self._users.create(
            User(
                id=None,
                username=payload.username.strip(),
                full_name=payload.full_name.strip(),
                password_hash=hash_password(payload.password),
                role=UserRole.CAJERO,
                is_active=True,
            )
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="CREATE_CASHIER",
                details=f"Cajero creado: {created.username}",
                ip_address=client_ip,
            )
        )
        return _to_user_out(created)

    def toggle_user(self, user_id: int, is_active: bool, actor: str, client_ip: str) -> UserOut:
        updated = self._users.set_active(user_id, is_active)
        if not updated:
            raise ResourceNotFoundError("Usuario no encontrado.")
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="TOGGLE_USER",
                details=f"Usuario {updated.username} is_active={is_active}",
                ip_address=client_ip,
            )
        )
        return _to_user_out(updated)

    def list_accounts(self) -> List[NequiAccountOut]:
        return [
            NequiAccountOut(
                id=a.id or 0,
                alias=a.alias,
                phone_number=a.phone_number,
                device_label=a.device_label,
                is_active=a.is_active,
                created_at=a.created_at,
            )
            for a in self._accounts.list_all()
        ]

    def create_account(self, payload: NequiAccountIn, actor: str, client_ip: str) -> NequiAccountOut:
        if self._accounts.get_by_alias(payload.alias.strip()):
            raise ForbiddenError("Ya existe una cuenta Nequi con ese alias.")
        created = self._accounts.create(
            NequiAccount(
                id=None,
                alias=payload.alias.strip(),
                phone_number=payload.phone_number.strip(),
                device_label=payload.device_label.strip(),
                is_active=True,
            )
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="CREATE_NEQUI_ACCOUNT",
                details=f"Alias={created.alias} Cel={created.phone_number}",
                ip_address=client_ip,
            )
        )
        return NequiAccountOut(
            id=created.id or 0,
            alias=created.alias,
            phone_number=created.phone_number,
            device_label=created.device_label,
            is_active=created.is_active,
            created_at=created.created_at,
        )

    def get_server_config(self) -> ServerConfigOut:
        cfg = self._config.get_settings()
        return ServerConfigOut(
            app_version=get_installed_version(),
            lan_ip=detect_lan_ip(),
            server_port=cfg.server_port,
            api_token=cfg.api_token,
            tts_enabled=cfg.tts_enabled,
            tts_voice=cfg.tts_voice,
            github_repo=cfg.github_repo,
            auto_update_enabled=cfg.auto_update_enabled,
            active_pos_clients=self._ws.get_active_client_count(),
            updated_at=cfg.updated_at,
        )

    def update_server_config(self, payload: UpdateConfigIn, actor: str, client_ip: str) -> ServerConfigOut:
        current = self._config.get_settings()
        saved = self._config.save_settings(
            ServerSettings(
                api_token=current.api_token,
                server_port=payload.server_port,
                tts_enabled=payload.tts_enabled,
                tts_voice=payload.tts_voice,
                github_repo=payload.github_repo.strip(),
                auto_update_enabled=payload.auto_update_enabled,
            )
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="UPDATE_CONFIG",
                details=f"Port={saved.server_port}, TTS={saved.tts_enabled}, Repo={saved.github_repo}",
                ip_address=client_ip,
            )
        )
        return self.get_server_config()

    def rotate_api_token(self, actor: str, client_ip: str) -> ServerConfigOut:
        current = self._config.get_settings()
        self._config.save_settings(
            ServerSettings(
                api_token=generate_device_api_token(),
                server_port=current.server_port,
                tts_enabled=current.tts_enabled,
                tts_voice=current.tts_voice,
                github_repo=current.github_repo,
                auto_update_enabled=current.auto_update_enabled,
            )
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="ROTATE_API_TOKEN",
                details="Token de vinculación Android rotado.",
                ip_address=client_ip,
            )
        )
        return self.get_server_config()

    async def check_updates(self) -> UpdateCheckOut:
        cfg = self._config.get_settings()
        updater = UnattendedUpdaterService()
        res = await updater.check_for_updates(cfg.github_repo)
        return UpdateCheckOut(
            status=res.status,
            current_version=res.current_version,
            latest_version=res.latest_version,
            update_available=res.update_available,
            message=res.message,
            release_notes=res.release_notes,
            server_download_url=res.server_download_url,
            client_download_url=res.client_download_url,
            sha256_sums_url=res.sha256_sums_url,
        )

    async def install_unattended_update(self, actor: str, client_ip: str) -> UpdateInstallOut:
        cfg = self._config.get_settings()
        updater = UnattendedUpdaterService()
        check = await updater.check_for_updates(cfg.github_repo)
        if not check.update_available:
            return UpdateInstallOut(
                status="up_to_date",
                message=check.message,
                target_version=check.current_version,
            )
        if not check.server_download_url:
            raise ResourceNotFoundError(
                "El release no contiene el ejecutable NequiPayPOS_Server_Win10_11.exe."
            )

        await updater.download_and_schedule_unattended_install(
            download_url=check.server_download_url,
            sha256_sums_url=check.sha256_sums_url,
        )
        self._audit.record(
            AuditLog(
                id=None,
                actor_username=actor,
                action="UNATTENDED_UPDATE",
                details=f"Actualización desatendida v{check.current_version} -> v{check.latest_version}",
                ip_address=client_ip,
            )
        )

        async def _exit_after_response() -> None:
            await asyncio.sleep(1.2)
            os._exit(0)

        asyncio.create_task(_exit_after_response())
        return UpdateInstallOut(
            status="installing",
            message=f"Actualizando desatendidamente a v{check.latest_version}. El servidor se reiniciará en segundos.",
            target_version=check.latest_version,
        )

    def generate_qr_config(self) -> QrConfigOut:
        cfg = self._config.get_settings()
        lan_ip = detect_lan_ip()
        payload = json.dumps(
            {
                "server_ip": lan_ip,
                "server_port": cfg.server_port,
                "api_token": cfg.api_token,
                "protocol": "http",
            },
            separators=(",", ":"),
        )
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_img = base64.b64encode(buf.getvalue()).decode("ascii")
        return QrConfigOut(
            qr_payload_json=payload,
            qr_image_base64=f"data:image/png;base64,{b64_img}",
            lan_ip=lan_ip,
            server_port=cfg.server_port,
        )

    async def test_sound(self, amount: Decimal) -> dict:
        phrase = build_tts_phrase(amount)
        audio_file = await self._tts.synthesize_deposit_phrase(phrase, f"test_{int(amount)}")
        payload = {
            "id": 0,
            "idempotency_hash": "test-sound",
            "account_id": 0,
            "account_alias": "PRUEBA DE AUDIO",
            "sender_name": "Sistema POS",
            "amount_cop": f"{amount:.2f}",
            "amount_words": monto_a_letras(amount),
            "tts_phrase": phrase,
            "audio_url": f"/static/audio/{audio_file}" if audio_file else None,
            "source": "MANUAL_TEST",
            "captured_at": datetime.utcnow().isoformat(),
            "received_at": datetime.utcnow().isoformat(),
        }
        await self._ws.broadcast_deposit(payload)
        return payload

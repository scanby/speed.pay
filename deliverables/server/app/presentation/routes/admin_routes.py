from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.dtos import (
    CreateCashierIn,
    NequiAccountIn,
    NequiAccountOut,
    QrConfigOut,
    ServerConfigOut,
    UpdateCheckOut,
    UpdateConfigIn,
    UpdateInstallOut,
    UserOut,
)
from app.application.use_cases import AdminUseCases
from app.domain.entities import User
from app.domain.exceptions import ForbiddenError, ResourceNotFoundError
from app.presentation.dependencies import get_admin_use_cases, require_admin

router = APIRouter(prefix="/api/admin", tags=["Administración"])


@router.get("/users", response_model=List[UserOut])
def list_users(
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> List[UserOut]:
    return use_cases.list_users()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_cashier(
    payload: CreateCashierIn,
    request: Request,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> UserOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        return use_cases.create_cashier(payload, admin.username, client_ip)
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch("/users/{user_id}/status", response_model=UserOut)
def toggle_user_status(
    user_id: int,
    is_active: bool = Query(...),
    request: Request = None,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> UserOut:
    client_ip = request.client.host if request and request.client else "unknown"
    try:
        return use_cases.toggle_user(user_id, is_active, admin.username, client_ip)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/accounts", response_model=List[NequiAccountOut])
def list_accounts(
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> List[NequiAccountOut]:
    return use_cases.list_accounts()


@router.post("/accounts", response_model=NequiAccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: NequiAccountIn,
    request: Request,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> NequiAccountOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        return use_cases.create_account(payload, admin.username, client_ip)
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/config", response_model=ServerConfigOut)
def get_config(
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> ServerConfigOut:
    return use_cases.get_server_config()


@router.put("/config", response_model=ServerConfigOut)
def update_config(
    payload: UpdateConfigIn,
    request: Request,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> ServerConfigOut:
    client_ip = request.client.host if request.client else "unknown"
    return use_cases.update_server_config(payload, admin.username, client_ip)


@router.post("/config/rotate-token", response_model=ServerConfigOut)
def rotate_token(
    request: Request,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> ServerConfigOut:
    client_ip = request.client.host if request.client else "unknown"
    return use_cases.rotate_api_token(admin.username, client_ip)


@router.get("/config/qr", response_model=QrConfigOut)
def get_qr_config(
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> QrConfigOut:
    return use_cases.generate_qr_config()


@router.post("/test-sound")
async def trigger_test_sound(
    amount: Decimal = Query(default=Decimal("50000"), gt=0),
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> dict:
    return await use_cases.test_sound(amount)


@router.get("/updates/check", response_model=UpdateCheckOut)
async def check_for_updates(
    _admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> UpdateCheckOut:
    return await use_cases.check_updates()


@router.post("/updates/install", response_model=UpdateInstallOut, status_code=status.HTTP_202_ACCEPTED)
async def install_unattended_update(
    request: Request,
    admin: User = Depends(require_admin),
    use_cases: AdminUseCases = Depends(get_admin_use_cases),
) -> UpdateInstallOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        return await use_cases.install_unattended_update(admin.username, client_ip)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

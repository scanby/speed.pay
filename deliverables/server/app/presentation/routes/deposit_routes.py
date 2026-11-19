from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.application.dtos import DailyDepositsOut, DepositIngestIn, DepositOut
from app.application.use_cases import DepositUseCases
from app.domain.entities import User
from app.domain.exceptions import DuplicateTransactionError, ForbiddenError
from app.presentation.dependencies import (
    get_current_user,
    get_deposit_use_cases,
    require_admin,
    require_device_token,
)

router = APIRouter(prefix="/api/deposits", tags=["Depósitos Nequi"])


@router.post(
    "/ingest",
    response_model=DepositOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_device_token)],
)
async def ingest_deposit(
    payload: DepositIngestIn,
    request: Request,
    use_cases: DepositUseCases = Depends(get_deposit_use_cases),
) -> DepositOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        return await use_cases.ingest_deposit(payload, client_ip)
    except DuplicateTransactionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/today", response_model=DailyDepositsOut)
def get_today_deposits(
    current_user: User = Depends(get_current_user),
    use_cases: DepositUseCases = Depends(get_deposit_use_cases),
) -> DailyDepositsOut:
    return use_cases.get_today_for_role(current_user.role)


@router.get("/history", response_model=List[DepositOut])
def get_history_deposits(
    start_date: date = Query(...),
    end_date: date = Query(...),
    account_id: Optional[int] = Query(default=None),
    _admin: User = Depends(require_admin),
    use_cases: DepositUseCases = Depends(get_deposit_use_cases),
) -> List[DepositOut]:
    return use_cases.get_history(start_date, end_date, account_id)


@router.get("/export")
def export_deposits_csv(
    start_date: date = Query(...),
    end_date: date = Query(...),
    account_id: Optional[int] = Query(default=None),
    _admin: User = Depends(require_admin),
    use_cases: DepositUseCases = Depends(get_deposit_use_cases),
) -> Response:
    csv_content = use_cases.export_csv(start_date, end_date, account_id)
    filename = f"nequipos_reporte_{start_date}_{end_date}.csv"
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..schemas.reports import (AgingResponse, DashboardKpiResponse,
                               ProfitLossResponse, StockPositionResponse,
                               TrialBalanceResponse)
from ..services.report_service import ReportService

router = APIRouter()


@router.get("/dashboard", response_model=DashboardKpiResponse)
async def dashboard_kpis(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "sales_manager"
        )
    ),
) -> DashboardKpiResponse:
    return await ReportService(db).dashboard_kpis()


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> TrialBalanceResponse:
    return await ReportService(db).trial_balance()


@router.get("/profit-loss", response_model=ProfitLossResponse)
async def profit_loss(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> ProfitLossResponse:
    return await ReportService(db).profit_loss()


@router.get("/stock-position", response_model=StockPositionResponse)
async def stock_position(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "inventory_manager"
        )
    ),
) -> StockPositionResponse:
    return await ReportService(db).stock_position()


@router.get("/ar-aging", response_model=list[AgingResponse])
async def ar_aging(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
):
    return await ReportService(db).ar_aging()


@router.get("/ap-aging", response_model=list[AgingResponse])
async def ap_aging(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
):
    return await ReportService(db).ap_aging()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..database import get_db
from ..dependencies import require_roles
from ..services.exchange_rate_service import ExchangeRateService
from ..models.exchange_rate import ExchangeRate

router = APIRouter()


@router.get('', response_model=list)
async def list_exchange_rates(db: AsyncSession = Depends(get_db), _=Depends(require_roles('super_admin','admin'))):
    items = await ExchangeRateService(db).list_rates()
    return items


@router.post('', response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_exchange_rate(payload: dict, db: AsyncSession = Depends(get_db), _=Depends(require_roles('super_admin','admin'))):
    try:
        currency_from = payload['currency_from']
        currency_to = payload['currency_to']
        rate = float(payload['rate'])
        effective = datetime.fromisoformat(payload.get('effective_date')) if payload.get('effective_date') else datetime.utcnow()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    er = await ExchangeRateService(db).create_rate(currency_from, currency_to, rate, effective)
    return {'id': er.id, 'currency_from': er.currency_from, 'currency_to': er.currency_to, 'rate': float(er.rate), 'effective_date': er.effective_date.isoformat()}

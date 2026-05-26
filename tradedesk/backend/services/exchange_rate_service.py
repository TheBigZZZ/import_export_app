from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.exchange_rate import ExchangeRate
import httpx
from ..config import settings
import asyncio
import json
from pathlib import Path


class ExchangeRateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_rates(self) -> list[ExchangeRate]:
        stmt = select(ExchangeRate).order_by(ExchangeRate.effective_date.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_rate(self, currency_from: str, currency_to: str, rate: float, effective_date: datetime) -> ExchangeRate:
        er = ExchangeRate(currency_from=currency_from.upper(), currency_to=currency_to.upper(), rate=rate, effective_date=effective_date)
        self.db.add(er)
        await self.db.commit()
        await self.db.refresh(er)
        return er

    async def sync_from_public(self, base: str | None = None, targets: list[str] | None = None, source_url: str | None = None) -> list[ExchangeRate]:
        """Fetch rates from public source and persist them.

        Returns list of created ExchangeRate objects.
        """
        base = (base or settings.exchange_rate_default_base).upper()
        targets = [t.upper() for t in (targets or settings.exchange_rate_default_targets)]
        source_url = source_url or settings.exchange_rate_source_url
        url = source_url.format(base=base)
        # Resiliency: retry with exponential backoff
        attempts = 3
        backoff = 2
        last_exc: Exception | None = None
        data = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, attempts + 1):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    last_exc = None
                    break
                except Exception as exc:  # pragma: no cover - external API failures
                    last_exc = exc
                    await asyncio.sleep(backoff ** attempt)

        status_path = Path(settings.data_dir) / "exchange_sync_status.json"
        status = {"last_success": None, "consecutive_failures": 0}
        try:
            if status_path.exists():
                status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            status = {"last_success": None, "consecutive_failures": 0}

        if data is None:
            # record failure
            status["consecutive_failures"] = status.get("consecutive_failures", 0) + 1
            status_path.write_text(json.dumps(status), encoding="utf-8")
            # Alert when failures cross threshold
            threshold = 3
            if status["consecutive_failures"] >= threshold:
                # send notifications (import locally to avoid circular imports)
                try:
                    to = settings.diagnostics_notify_email_to
                    if to:
                        from .email_service import send_simple_email as _send_email

                        await asyncio.to_thread(_send_email, to, "Exchange rate sync failure", f"Exchange rate sync has failed {status['consecutive_failures']} times. Last error: {last_exc}")
                except Exception:
                    pass
                try:
                    sms_to = None
                    if settings.sms_provider:
                        sms_to = settings.sms_from_number
                    if sms_to:
                        from .sms_service import send_sms as _send_sms

                        await asyncio.to_thread(_send_sms, sms_to, f"Exchange sync failures: {status['consecutive_failures']}")
                except Exception:
                    pass
            raise last_exc
        rates = data.get('rates') or {}
        created: list[ExchangeRate] = []
        eff = datetime.utcnow()
        async with self.db.begin():
            for tgt in targets:
                if tgt == base:
                    continue
                rate = rates.get(tgt)
                if rate is None:
                    continue
                er = ExchangeRate(currency_from=base, currency_to=tgt, rate=float(rate), effective_date=eff)
                self.db.add(er)
                created.append(er)
        await self.db.commit()
        # record success
        try:
            status["last_success"] = eff.isoformat()
            status["consecutive_failures"] = 0
            status_path.write_text(json.dumps(status), encoding="utf-8")
        except Exception:
            pass
        return created

    async def get_latest(self, currency_from: str, currency_to: str) -> ExchangeRate | None:
        stmt = select(ExchangeRate).where(ExchangeRate.currency_from == currency_from.upper(), ExchangeRate.currency_to == currency_to.upper()).order_by(ExchangeRate.effective_date.desc())
        res = await self.db.execute(stmt)
        return res.scalars().first()

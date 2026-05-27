from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import event, inspect

from .live import LiveEvent, broadcast_live_event

from .models import (
    BankAccount,
    ChartOfAccount,
    Customer,
    Expense,
    ImportShipment,
    ImportShipmentItem,
    Product,
    PurchaseOrder,
    SalesInvoice,
    SalesInvoiceItem,
    Supplier,
    Transaction,
    User,
)
from .models.audit_log import AuditLog

AUDITED_MODELS = [
    User,
    ChartOfAccount,
    BankAccount,
    Transaction,
    Customer,
    Supplier,
    Product,
    ImportShipment,
    ImportShipmentItem,
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseOrder,
    Expense,
]


def _to_jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _snapshot(target) -> dict:
    data = {}
    for column in target.__table__.columns:
        data[column.name] = _to_jsonable(getattr(target, column.name))
    return data


def _old_snapshot(target) -> dict:
    state = inspect(target)
    old_data = {}
    for attr in state.mapper.column_attrs:
        hist = state.attrs[attr.key].history
        if hist.deleted:
            old_data[attr.key] = _to_jsonable(hist.deleted[0])
        else:
            old_data[attr.key] = None
    return old_data


def _insert_audit(connection, action_type: str, target, old_value: dict | None, new_value: dict | None) -> None:
    user_id = getattr(target, "created_by", None)
    record_id = getattr(target, "id", None)
    connection.execute(
        AuditLog.__table__.insert().values(
            user_id=user_id,
            action_type=action_type,
            table_name=target.__tablename__,
            record_id=record_id,
            old_value=json.dumps(old_value) if old_value is not None else None,
            new_value=json.dumps(new_value) if new_value is not None else None,
            ip_address="127.0.0.1",
            action_time=datetime.now(UTC),
        )
    )


def _after_insert(mapper, connection, target) -> None:
    _insert_audit(connection, "insert", target, old_value=None, new_value=_snapshot(target))
    broadcast_live_event(
        LiveEvent(
            event_type="entity.changed",
            table_name=target.__tablename__,
            action="insert",
            record_id=getattr(target, "id", None),
            user_id=getattr(target, "created_by", None),
        )
    )


def _after_update(mapper, connection, target) -> None:
    _insert_audit(connection, "update", target, old_value=_old_snapshot(target), new_value=_snapshot(target))
    broadcast_live_event(
        LiveEvent(
            event_type="entity.changed",
            table_name=target.__tablename__,
            action="update",
            record_id=getattr(target, "id", None),
            user_id=getattr(target, "created_by", None),
        )
    )


def _after_delete(mapper, connection, target) -> None:
    _insert_audit(connection, "delete", target, old_value=_snapshot(target), new_value=None)
    broadcast_live_event(
        LiveEvent(
            event_type="entity.changed",
            table_name=target.__tablename__,
            action="delete",
            record_id=getattr(target, "id", None),
            user_id=getattr(target, "created_by", None),
        )
    )


def register_audit_listeners() -> None:
    if getattr(register_audit_listeners, "_registered", False):
        return
    for model in AUDITED_MODELS:
        event.listen(model, "after_insert", _after_insert)
        event.listen(model, "after_update", _after_update)
        event.listen(model, "after_delete", _after_delete)

    register_audit_listeners._registered = True


register_audit_listeners()

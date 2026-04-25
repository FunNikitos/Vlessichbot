"""Audit log helper — структурированный аудит важных действий.
Пишется в audit_logs (видим из owner-панели в будущем)."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


async def audit(
    *,
    actor_type: str,
    actor_id: int,
    action: str,
    payload: dict[str, Any] | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Persist audit record. Не падает наружу."""
    body = json.dumps(payload, ensure_ascii=False) if payload else None
    try:
        if session is not None:
            session.add(
                AuditLog(
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    payload=body,
                )
            )
            await session.commit()
            return
        async with SessionLocal() as s:
            s.add(
                AuditLog(
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    payload=body,
                )
            )
            await s.commit()
    except Exception:  # noqa: BLE001
        log.exception("audit() failed")

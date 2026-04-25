"""Helpers to persist runtime errors into ErrorLog (visible via /errors)."""
from __future__ import annotations

import logging
import traceback

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ErrorLog
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


async def log_error(
    *,
    source: str,
    message: str,
    level: str = "error",
    user_id: int | None = None,
    exc: BaseException | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Записать ошибку в БД. Никогда не падает сама."""
    details = "".join(traceback.format_exception(exc)) if exc else None
    try:
        if session is not None:
            session.add(
                ErrorLog(
                    level=level,
                    source=source,
                    message=message[:500],
                    details=details,
                    user_id=user_id,
                )
            )
            await session.commit()
            return
        async with SessionLocal() as s:
            s.add(
                ErrorLog(
                    level=level,
                    source=source,
                    message=message[:500],
                    details=details,
                    user_id=user_id,
                )
            )
            await s.commit()
    except Exception:  # noqa: BLE001
        log.exception("Failed to persist error to ErrorLog")

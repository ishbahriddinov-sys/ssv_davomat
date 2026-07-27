"""Сервис журналирования действий (аудит)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionLog


async def log_action(
    session: AsyncSession,
    action: str,
    *,
    actor_id: int | None = None,
    actor_telegram_id: int | None = None,
    entity: str | None = None,
    entity_id: str | int | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> None:
    entry = ActionLog(
        actor_id=actor_id,
        actor_telegram_id=actor_telegram_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
        ip_address=ip_address,
    )
    session.add(entry)
    await session.flush()

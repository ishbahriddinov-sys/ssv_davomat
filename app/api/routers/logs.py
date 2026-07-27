"""API журнала действий (аудит)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.enums import Role
from app.db.models import ActionLog, AdminUser
from app.db.session import get_db

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def list_logs(
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    res = await session.execute(
        select(ActionLog).order_by(desc(ActionLog.created_at)).limit(limit)
    )
    return [
        {
            "id": log.id,
            "created_at": log.created_at.isoformat(),
            "action": log.action,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "actor_id": log.actor_id,
            "actor_telegram_id": log.actor_telegram_id,
            "details": log.details,
        }
        for log in res.scalars().all()
    ]

"""Usage tracking for token consumption and billing.

Tracks per-tenant and per-user LLM usage for billing and limits.
"""
import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.models.user_model import UserModel
from src.infrastructure.db.models.session_model import SessionModel

logger = logging.getLogger(__name__)


class UsageTracker:
    """Track LLM token usage per tenant and user."""

    async def track_tokens(
        self,
        session_id: str,
        tokens_used: int,
        db: AsyncSession,
    ) -> bool:
        """Track token usage for billing and limits.

        Returns True if within limits, False if exceeded.
        """
        if tokens_used <= 0:
            return True

        # Get tenant from session
        result = await db.execute(
            select(SessionModel.tenant_id, SessionModel.user_id)
            .where(SessionModel.id == session_id)
        )
        row = result.one_or_none()
        if not row:
            logger.warning(f"[Usage] Session not found: {session_id}")
            return False

        tenant_id, user_id = row

        # Check tenant limits
        tenant_result = await db.execute(
            select(TenantModel.tokens_used, TenantModel.max_tokens_monthly)
            .where(TenantModel.id == tenant_id)
        )
        tenant_row = tenant_result.one_or_none()

        if tenant_row:
            current, limit = tenant_row
            if current + tokens_used > limit:
                logger.warning(
                    f"[Usage] Tenant limit exceeded: {tenant_id} "
                    f"({current + tokens_used}/{limit})"
                )
                return False

            # Update tenant usage
            await db.execute(
                update(TenantModel)
                .where(TenantModel.id == tenant_id)
                .values(tokens_used=TenantModel.tokens_used + tokens_used)
            )

        # Update user usage
        await db.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_active_at=db.bind.engine.execution_options().get("server_version", None))
        )

        await db.commit()
        logger.info(f"[Usage] Tracked {tokens_used} tokens for {tenant_id}/{user_id}")
        return True

    async def get_usage_stats(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> dict:
        """Get usage statistics for tenant."""
        result = await db.execute(
            select(TenantModel.tokens_used, TenantModel.max_tokens_monthly, TenantModel.cost_cents)
            .where(TenantModel.id == tenant_id)
        )
        row = result.one_or_none()

        if not row:
            return {"error": "Tenant not found"}

        tokens_used, limit, cost = row
        remaining = max(0, limit - tokens_used)
        percentage = (tokens_used / limit * 100) if limit > 0 else 0

        return {
            "tenant_id": tenant_id,
            "tokens_used": tokens_used,
            "tokens_limit": limit,
            "tokens_remaining": remaining,
            "usage_percentage": round(percentage, 2),
            "cost_cents": cost,
        }

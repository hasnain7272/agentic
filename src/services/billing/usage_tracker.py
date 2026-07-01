"""
SaaS Billing & Telemetry Tracker.
Tracks token usage across the platform to enable Stripe metered billing.
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.queue.redis_streams_broker import get_streams_broker

logger = logging.getLogger(__name__)

class QuotaExceededError(Exception):
    pass

class UsageTracker:
    @staticmethod
    async def check_quota(db: AsyncSession, tenant_id: str):
        """Check if tenant has exceeded their billing quota."""
        from sqlalchemy import select
        from src.infrastructure.db.models.tenant_model import TenantModel
        
        if tenant_id == "local":
            return
            
        result = await db.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant:
            current_spend_usd = tenant.cost_cents / 100.0
            try:
                quota = float(tenant.quota_usd) if tenant.quota_usd else 50.0
            except (ValueError, TypeError):
                quota = 50.0

            if current_spend_usd >= quota:
                logger.warning(f"[Billing] Tenant {tenant_id} exceeded quota: ${current_spend_usd} >= ${quota}")
                raise QuotaExceededError(f"Billing quota exceeded. Current spend: ${current_spend_usd:.2f}, Quota: ${quota:.2f}")

    @staticmethod
    async def track_llm_usage(
        session_id: str, 
        tenant_id: str, 
        task_id: str, 
        model: str, 
        usage: Optional[Any]
    ):
        """Track LLM token usage for metered billing."""
        if not usage:
            return
            
        prompt_tokens = getattr(usage, "prompt_tokens", 0)
        completion_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)
        
        if total_tokens == 0:
            return

        payload = {
            "event_type": "LLM_USAGE",
            "tenant_id": tenant_id,
            "session_id": session_id,
            "task_id": task_id,
            "model": model,
            "metrics": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        }
        
        try:
            broker = await get_streams_broker()
            # Push to a telemetry stream for asynchronous billing aggregation
            await broker.publish("telemetry:billing", payload, tenant_id=tenant_id)
            logger.info(f"[Billing] Tracked {total_tokens} tokens for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"[Billing] Failed to track usage: {e}")

usage_tracker = UsageTracker()

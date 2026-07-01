import asyncio
# pyrefly: ignore [missing-import]
from src.infrastructure.db.session import AsyncSessionLocal
from src.services.agent_loop.brain.config_loader import load_session_llm_config
from src.infrastructure.db.models.tenant_model import TenantModel

async def test():
    async with AsyncSessionLocal() as session:
        from src.infrastructure.db.models.session_model import SessionModel
        from sqlalchemy import select
        
        result = await session.execute(select(SessionModel).order_by(SessionModel.created_at.desc()).limit(1))
        s = result.scalar_one_or_none()
        if s:
            print(f"Testing session {s.id}")
            print(f"Tenant ID: {s.tenant_id}")
            print(f"Context: {s.context}")
            
            result2 = await session.execute(select(TenantModel).where(TenantModel.id == s.tenant_id))
            tenant = result2.scalar_one_or_none()
            if tenant:
                print(f"Tenant Config: {tenant.config}")
            else:
                print("No tenant found!")
                
            cfg = await load_session_llm_config(session, s.id, s)
            print("Loaded config:", cfg)

asyncio.run(test())

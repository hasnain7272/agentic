"""
Tests for LangGraph integration and Native Skills performance
"""
import asyncio
import time
import uuid
from pathlib import Path
from agentcore.loop.skills import read_file, write_file, patch_file, list_dir, grep_search
from agentcore.loop.agents import ManagementAgent
from agentcore.loop.state import AgentContext
from agentcore.database import init_db, get_db_manager, SessionModel, UserModel, TenantModel, UserRole
from sqlalchemy import select

async def test_native_skills_performance(tmp_path):
    # Verify write_file
    file_path = tmp_path / "speed_test.txt"
    start_time = time.perf_counter()
    write_res = await write_file(str(file_path), "Hello from Native Skills!\nLine 2\nLine 3")
    write_duration = time.perf_counter() - start_time
    
    assert write_res["written_bytes"] > 0
    assert file_path.exists()
    print(f"\n[Native Skills] write_file execution took: {write_duration*1000:.3f} ms")
    
    # Verify read_file
    start_time = time.perf_counter()
    read_res = await read_file(str(file_path), start_line=1, end_line=2)
    read_duration = time.perf_counter() - start_time
    
    assert "1: Hello from Native Skills!" in read_res["content"]
    assert "2: Line 2" in read_res["content"]
    print(f"[Native Skills] read_file (ranged) execution took: {read_duration*1000:.3f} ms")

async def test_graph_conversation_route():
    # Setup database structure for test run
    await init_db()
    
    # Ensure a tenant and user exist
    async with get_db_manager().session() as db:
        tenant_res = await db.execute(select(TenantModel).limit(1))
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            tenant = TenantModel(id="test-tenant", slug="test-tenant", name="Test Tenant")
            db.add(tenant)
            
        user_res = await db.execute(select(UserModel).limit(1))
        user = user_res.scalar_one_or_none()
        if not user:
            user = UserModel(id="test-user", email="test@example.com", name="Test", password_hash="hash", tenant_id="test-tenant", role=UserRole.developer)
            db.add(user)
            
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        task_id = f"test-task-{uuid.uuid4().hex[:8]}"
        
        session = SessionModel(id=session_id, tenant_id="test-tenant", user_id="test-user", title="Test Session")
        db.add(session)
        await db.commit()
        
    context = AgentContext(
        session_id=session_id,
        task_id=task_id,
        user_id="test-user",
        tenant_id="test-tenant",
        user_role="developer"
    )
    
    async with get_db_manager().session() as db:
        agent = ManagementAgent(session_id=session_id, db_session=db, context=context)
        
        events = []
        async for event in agent.run("Hello there! Just say hi back."):
            events.append(event)
            
        print("\n[LangGraph PGE] Event stream yielded:")
        for ev in events:
            print(f"  - {ev}")
            
        # Verify routing and streaming structure
        assert len(events) > 0
        assert any(e.get("type") == "completed" for e in events)
        assert any(e.get("type") == "done" for e in events)

if __name__ == "__main__":
    import tempfile
    async def main():
        print("Running native skills performance test...")
        with tempfile.TemporaryDirectory() as tmpdir:
            await test_native_skills_performance(Path(tmpdir))
        
        print("\nRunning graph conversation route test...")
        await test_graph_conversation_route()
        print("\nAll tests completed successfully!")
        
    asyncio.run(main())

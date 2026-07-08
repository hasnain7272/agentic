"""
Tests for CrewAI Dynamic Worker: Step limit protection and prompt structure
"""
import asyncio
from langchain_core.messages import HumanMessage
from agentcore.loop.graph_state import AgentState
from agentcore.loop.graph import dynamic_worker_node
from langgraph.errors import GraphInterrupt

async def test_step_limit_protection():
    print("Running step limit protection verification...")
    
    state: AgentState = {
        "messages": [HumanMessage(content="Write some code.")],
        "step_count": 25, # On the next run, step count becomes 26, which should trigger protection
        "session_id": "test-sess",
        "task_id": "test-task",
        "tenant_id": "local",
        "user_id": "local",
        "user_role": "developer",
        "route": "PGE",
        "modified_files": [],
        "agents": [{"role": "Developer", "goal": "Solve task", "backstory": "developer", "skills": []}],
        "tasks": [{"id": "task_1", "description": "Write code", "expected_output": "code", "assigned_to": "Developer", "status": "todo", "output": ""}],
        "active_issue_id": "task_1"
    }
    
    config = {
        "configurable": {
            "context": {},
            "callback": None
        }
    }
    
    try:
        await dynamic_worker_node(state, config)
        assert False, "Should have raised GraphInterrupt"
    except GraphInterrupt as gi:
        print(f"[Success] Graph paused correctly on step limit: {gi}")

if __name__ == "__main__":
    asyncio.run(test_step_limit_protection())
    print("\nAll CrewAI Dynamic Worker loop tests completed successfully!")

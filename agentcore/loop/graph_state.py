"""
AgentCore Graph State — LangGraph AgentState schema definition
"""
from typing import List, Dict, Any, TypedDict, Annotated
from langgraph.graph.message import add_messages

class DynamicAgentCard(TypedDict):
    role: str
    goal: str
    backstory: str
    skills: List[str]

class DynamicTask(TypedDict):
    id: str
    description: str
    expected_output: str
    assigned_to: str
    status: str               # "todo" | "done"
    output: str

class AgentState(TypedDict):
    # Core fields
    messages: Annotated[list, add_messages]
    session_id: str
    task_id: str
    tenant_id: str
    user_id: str
    user_role: str
    
    # Routing
    route: str  # CONVERSATION, INSPECT, PGE
    
    # CrewAI Dynamic Fields
    agents: List[DynamicAgentCard]
    tasks: List[DynamicTask]
    modified_files: List[str]
    step_count: int            # Prevents runaway loops

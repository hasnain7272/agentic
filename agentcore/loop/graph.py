"""
AgentCore Graph Orchestration — LangGraph StateGraph nodes, edges, and compilation.
"""
import json
import os
import logging
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt

from agentcore.loop.graph_state import AgentState
from agentcore.loop.skills import NATIVE_SKILLS, NATIVE_SKILLS_SCHEMAS
from agentcore.loop.llm import LLMCaller
from agentcore.database import (
    get_db_manager, add_message, ToolCallModel, ApprovalModel, MessageModel
)
from agentcore.governance import check_destructive
from sqlalchemy import select

logger = logging.getLogger(__name__)

# =============================================================================
# UTILITIES
# =============================================================================

def convert_messages(messages) -> List[Dict[str, Any]]:
    """Convert LangChain message objects to LiteLLM JSON format."""
    converted = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            converted.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            converted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            m = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}
                    }
                    for tc in msg.tool_calls
                ]
            converted.append(m)
        elif isinstance(msg, ToolMessage):
            converted.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
                "content": msg.content
            })
        elif isinstance(msg, dict):
            converted.append(msg)
    return converted

# =============================================================================
# GRAPH NODES
# =============================================================================

async def classify_input_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Classify the input user prompt to route the execution flow."""
    last_msg = state["messages"][-1].content
    
    CLASSIFIER_PROMPT = """Analyze the user's message.
Classify it into one of these three categories:
- CONVERSATION: If it is a simple greeting, greeting reply, general conversation, or general question that does NOT need to read files, run commands, or inspect the workspace.
- INSPECT: If it is a request to read, view, list, search, or inspect files, logs, or workspace state without making any code edits.
- PGE: If it is a task to build, edit, refactor, or delete code/files in the workspace.

Output exactly "CONVERSATION", "INSPECT", or "PGE"."""

    llm = LLMCaller()
    context = config.get("configurable", {}).get("context")
    
    class_accum = []
    try:
        async for chunk in llm.call(
            [{"role": "user", "content": f"{CLASSIFIER_PROMPT}\n\nUser Request: \"{last_msg}\"\nOutput:"}],
            stream=True,
            context=context
        ):
            if chunk["type"] == "token":
                class_accum.append(chunk["text"])
    except Exception as e:
        logger.error(f"Classification call failed: {e}")
        
    class_out = "".join(class_accum).strip().upper()
    route = "PGE"
    for r in ["CONVERSATION", "INSPECT", "PGE"]:
        if r in class_out:
            route = r
            break
            
    return {"route": route}


async def direct_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Runs a direct conversation agent with optional tools execution."""
    callback = config.get("configurable", {}).get("callback")
    context = config.get("configurable", {}).get("context")
    
    if callback:
        await callback({"type": "reasoning", "text": "Thinking...\n"})
        
    llm = LLMCaller()
    converted = convert_messages(state["messages"])
    
    tools = NATIVE_SKILLS_SCHEMAS if state["route"] == "INSPECT" else None
    tokens = []
    reasonings = []
    tool_calls = []
    
    async for chunk in llm.call(
        converted,
        tools=tools,
        stream=True,
        context=context
    ):
        if chunk["type"] == "reasoning":
            if callback:
                await callback({"type": "reasoning", "text": chunk["text"]})
            reasonings.append(chunk["text"])
        elif chunk["type"] == "token":
            if callback:
                await callback({"type": "token", "text": chunk["text"]})
            tokens.append(chunk["text"])
        elif chunk["type"] == "tool_calls":
            tool_calls = chunk["calls"]
            tokens.append(chunk["content"])
            
    assistant_text = "".join(tokens)
    reasoning_text = "".join(reasonings) if reasonings else None
    
    # Fallback to parse structured text tool call format
    if not tool_calls and assistant_text:
        from agentcore.loop.agents import parse_text_tool_call
        parsed = parse_text_tool_call(assistant_text)
        if parsed:
            tool_calls = [{
                "id": "call_" + uuid.uuid4().hex[:8],
                "type": "function",
                "function": {"name": parsed["name"], "arguments": json.dumps(parsed["arguments"])}
            }]
            assistant_text = ""
            
    langchain_tool_calls = []
    for tc in tool_calls:
        try:
            args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
        except Exception:
            args = {}
        langchain_tool_calls.append({
            "name": tc["function"]["name"],
            "args": args,
            "id": tc["id"],
            "type": "tool_call"
        })
        
    ai_msg = AIMessage(content=assistant_text, tool_calls=langchain_tool_calls)
    if not langchain_tool_calls and callback:
        await callback({"type": "completed", "content": assistant_text})
        
    # Save the assistant message in database for UI persistence on page refresh
    session_id = state.get("session_id")
    task_id = state.get("task_id")
    async with get_db_manager().session() as db:
        db_tool_calls = []
        for tc in tool_calls:
            db_tool_calls.append({
                "id": tc["id"],
                "type": tc.get("type", "function"),
                "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
            })
        db_msg = MessageModel(
            session_id=session_id,
            task_id=task_id,
            role="assistant",
            content=assistant_text,
            reasoning=reasoning_text,
            tool_calls=db_tool_calls if db_tool_calls else None
        )
        db.add(db_msg)
        await db.commit()
        
    return {"messages": [ai_msg]}


async def tool_executor_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Central node for executing Native Skills and custom MCP tools with approvals verification."""
    callback = config.get("configurable", {}).get("callback")
    context = config.get("configurable", {}).get("context")
    task_id = state.get("task_id")
    session_id = state.get("session_id")
    
    last_msg = state["messages"][-1]
    tool_messages = []
    modified_files = list(state.get("modified_files", []))
    
    for tc in last_msg.tool_calls:
        func_name = tc["name"]
        args = tc["args"]
        tc_id = tc["id"]
        
        # Destructive tool approval check
        if await check_destructive(func_name, args):
            is_approved = False
            async with get_db_manager().session() as db:
                try:
                    res = await db.execute(
                        select(ToolCallModel).where(
                            ToolCallModel.task_id == task_id,
                            ToolCallModel.name == func_name,
                            ToolCallModel.status == "approved"
                        )
                    )
                    approved_calls = res.scalars().all()
                    for call in approved_calls:
                        call_args = call.arguments
                        if isinstance(call_args, str):
                            try:
                                call_args = json.loads(call_args)
                            except Exception:
                                pass
                        if call_args == args:
                            is_approved = True
                            break
                except Exception as e:
                    logger.error(f"Failed to check tool approval: {e}")
                    
            if not is_approved:
                # Trigger pending approval in DB
                approval_id = f"appr-{uuid.uuid4().hex[:12]}"
                async with get_db_manager().session() as db:
                    res = await db.execute(
                        select(MessageModel).where(
                            MessageModel.task_id == task_id,
                            MessageModel.role == "assistant"
                        ).order_by(MessageModel.created_at.desc())
                    )
                    last_db_msg = res.scalars().first()
                    if last_db_msg:
                        meta = dict(last_db_msg.meta or {})
                        meta["approval_id"] = approval_id
                        last_db_msg.meta = meta
                        db.add(last_db_msg)
                        
                    approval = ApprovalModel(
                        id=approval_id,
                        tenant_id=state.get("tenant_id", "local"),
                        requester_id=state.get("user_id", "local"),
                        action=func_name,
                        resource=args.get("path") or args.get("command") or args.get("query"),
                        context={"tool_call_id": tc_id, "arguments": args},
                        reason="Destructive action requires approval",
                        status="pending"
                    )
                    db.add(approval)
                    
                    tc_model = ToolCallModel(
                        id=tc_id,
                        task_id=task_id,
                        session_id=session_id,
                        name=func_name,
                        arguments=args,
                        status="pending",
                        approval_required=True
                    )
                    db.add(tc_model)
                    await db.commit()
                    
                if callback:
                    await callback({"type": "approval_required", "id": tc_id, "name": func_name, "arguments": args})
                    
                raise GraphInterrupt(f"Approval required for destructive tool: {func_name}")
                
        if callback:
            await callback({"type": "tool_executing", "id": tc_id, "tool": func_name, "message": f"Executing tool {func_name}..."})
            
        res_str = ""
        if func_name in NATIVE_SKILLS:
            try:
                res = await NATIVE_SKILLS[func_name](**args)
                if isinstance(res, dict) and "content" in res:
                    res_str = res["content"]
                elif isinstance(res, dict) and "written_bytes" in res:
                    res_str = f"Successfully wrote {res['written_bytes']} bytes to {res['path']}"
                else:
                    res_str = json.dumps(res)
            except Exception as e:
                res_str = f"Error executing native skill {func_name}: {e}"
        else:
            from agentcore.loop.agents import ManagementAgent
            async with get_db_manager().session() as db:
                agent = ManagementAgent(session_id=session_id, db_session=db, context=context)
                res_str = await agent._execute_local_tool(func_name, args)
                
        if callback:
            await callback({"type": "tool_result", "id": tc_id, "name": func_name, "result": {"success": "Error" not in res_str, "data": res_str}})
            
        async with get_db_manager().session() as db:
            try:
                tc_res = await db.execute(select(ToolCallModel).where(ToolCallModel.id == tc_id))
                tc_obj = tc_res.scalar_one_or_none()
                if tc_obj:
                    tc_obj.status = "completed" if "Error" not in res_str else "failed"
                    tc_obj.result = res_str
                    tc_obj.completed_at = datetime.utcnow()
                else:
                    tc_obj = ToolCallModel(
                        id=tc_id,
                        task_id=task_id,
                        session_id=session_id,
                        name=func_name,
                        arguments=args,
                        status="completed" if "Error" not in res_str else "failed",
                        result=res_str,
                        completed_at=datetime.utcnow()
                    )
                db.add(tc_obj)
                
                db_tool_msg = MessageModel(
                    session_id=session_id,
                    task_id=task_id,
                    role="tool",
                    content=res_str,
                    tool_call_id=tc_id,
                    meta={"tool_name": func_name}
                )
                db.add(db_tool_msg)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save tool results in DB: {e}")
                
        if func_name in ("write_file", "patch_file") and "path" in args:
            modified_files.append(args["path"])
            
        tool_messages.append(ToolMessage(content=res_str, name=func_name, tool_call_id=tc_id))
        
    return {"messages": tool_messages, "modified_files": modified_files}


import pickle
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from redis.asyncio import Redis

def _clean_config(config: Any) -> Any:
    if isinstance(config, dict):
        cleaned = {}
        for k, v in config.items():
            if k == "callback" or callable(v):
                continue
            cleaned[k] = _clean_config(v)
        return cleaned
    elif isinstance(config, list):
        return [_clean_config(item) for item in config]
    elif isinstance(config, tuple):
        return tuple(_clean_config(item) for item in config if not callable(item))
    elif callable(config):
        return None
    return config

class AsyncRedisSaver(BaseCheckpointSaver):
    """Custom Redis-based checkpointer for LangGraph state persistence."""
    def __init__(self, connection_string: str = "redis://localhost:6379"):
        super().__init__()
        self.redis = Redis.from_url(connection_string)

    async def aget_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
            key = f"checkpoint:{thread_id}:{checkpoint_ns}"
            
            data = await self.redis.get(key)
            if not data:
                return None
                
            snapshot = pickle.loads(data)
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": snapshot["parent_checkpoint_id"]
                }
            } if snapshot.get("parent_checkpoint_id") else None
            
            return CheckpointTuple(
                config=config,
                checkpoint=snapshot["checkpoint"],
                metadata=snapshot["metadata"],
                parent_config=parent_config
            )
        except Exception as e:
            logger.warning(f"Redis get checkpoint failed: {e}. Falling back.")
            return None

    async def aput(self, config: dict, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> dict:
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
            key = f"checkpoint:{thread_id}:{checkpoint_ns}"
            
            clean_checkpoint = _clean_config(checkpoint)
            clean_metadata = _clean_config(metadata)
            parent_id = config["configurable"].get("checkpoint_id")
            
            snapshot = {
                "checkpoint": clean_checkpoint,
                "metadata": clean_metadata,
                "parent_checkpoint_id": parent_id
            }
            await self.redis.set(key, pickle.dumps(snapshot))
        except Exception as e:
            logger.warning(f"Redis put checkpoint failed: {e}. Falling back.")
        return config


async def crew_planner_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyzes the request and dynamically constructs specialized worker profiles and task issues."""
    callback = config.get("configurable", {}).get("callback")
    context = config.get("configurable", {}).get("context")
    task_id = state.get("task_id")
    session_id = state.get("session_id")
    user_message = state["messages"][-1].content
    
    if callback:
        await callback({"type": "reasoning", "text": "### Crew Planner Node\nSpawning a custom agent crew and planning tasks on-the-fly...\n\n"})
        
    PLANNER_SYSTEM_PROMPT = """You are the Crew Planner Agent. Decompose the user request into:
1. A Crew of 1-3 specialized agent cards (role, goal, backstory, skills).
2. A checklist of 1-5 atomic Tasks (id, description, expected_output, assigned_to).

Format your output exactly as a JSON block:
{
  "agents": [
    {
      "role": "Researcher",
      "goal": "Explain target goal...",
      "backstory": "Explain backstory...",
      "skills": ["grep_search", "read_file"]
    }
  ],
  "tasks": [
    {
      "id": "task_1",
      "description": "Decomposed specific step...",
      "expected_output": "What is expected...",
      "assigned_to": "Researcher"
    }
  ]
}"""

    llm = LLMCaller()
    planner_accum = []
    async for chunk in llm.call(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        stream=True,
        context=context
    ):
        if chunk["type"] == "token":
            planner_accum.append(chunk["text"])
            
    planner_output = "".join(planner_accum)
    
    agents = []
    tasks = []
    from agentcore.loop.agents import extract_first_json_object
    json_str = extract_first_json_object(planner_output)
    if json_str:
        try:
            data = json.loads(json_str)
            agents = data.get("agents", [])
            tasks = data.get("tasks", [])
        except Exception:
            pass
            
    if not tasks:
        agents = [{
            "role": "Developer",
            "goal": "Solve the coding task",
            "backstory": "Expert developer.",
            "skills": ["write_file", "patch_file", "grep_search", "read_file", "bash_exec"]
        }]
        tasks = [{
            "id": "task_1",
            "description": f"Solve task: {user_message}",
            "expected_output": "Working code modifications",
            "assigned_to": "Developer",
            "status": "todo",
            "output": ""
        }]
    else:
        # Initialize default values
        for t in tasks:
            t["status"] = "todo"
            t["output"] = ""
            
    intro = "### Dynamic Crew Spawned\n\n"
    intro += "**Agents:**\n"
    for a in agents:
        intro += f"- **{a['role']}**: {a['goal']}\n"
    intro += "\n**Tasks:**\n"
    for t in tasks:
        intro += f"- [{t['id']}] {t['description']} (Assigned: {t['assigned_to']})\n"
        
    async with get_db_manager().session() as db:
        await add_message(db, session_id, "assistant", intro, task_id=task_id)
        await db.commit()
        
    if callback:
        await callback({"type": "token", "text": intro + "\n\n"})
        
    return {"agents": agents, "tasks": tasks, "active_issue_id": tasks[0]["id"] if tasks else ""}


async def dynamic_worker_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Runs a dynamically defined ReAct agent to solve its assigned task."""
    callback = config.get("configurable", {}).get("callback")
    context = config.get("configurable", {}).get("context")
    task_id = state.get("task_id")
    session_id = state.get("session_id")
    
    steps = state.get("step_count", 0) + 1
    if steps > 25:
        raise GraphInterrupt("Maximum sandbox execution steps (25) reached. Pausing for user feedback.")
        
    tasks = state.get("tasks", [])
    active_id = state.get("active_issue_id")
    
    # Check if we need to select the next pending task
    active_task = next((t for t in tasks if t["id"] == active_id), None)
    if not active_task or active_task.get("status") == "done":
        next_task = next((t for t in tasks if t.get("status") == "todo"), None)
        if next_task:
            active_id = next_task["id"]
            active_task = next_task
        else:
            return {} # All tasks finished
            
    agents = state.get("agents", [])
    card = next((a for a in agents if a["role"] == active_task["assigned_to"]), None)
    if not card:
        card = {
            "role": active_task["assigned_to"],
            "goal": "Complete the task",
            "backstory": "Competent AI employee",
            "skills": []
        }
        
    if callback:
        await callback({"type": "reasoning", "text": f"### Dynamic Worker: {card['role']} [Step {steps}/25]\nExecuting task: {active_task['description']}\n\n"})
        
    SYSTEM_PROMPT = f"""You are the {card['role']} Agent.
Your Goal: {card['goal']}
Your Backstory: {card['backstory']}

Your current task is: {active_task['description']}
Expected output: {active_task['expected_output']}

### Cross-Project File Access:
- You have unrestricted access to the entire local filesystem.
- If the user refers to "the other project" or files outside the current directory, you can read, write, list, and grep them directly by passing their absolute path (e.g. "C:/path/to/other_project") to your tools.

### Workspace Customization Rules & Skills:
- Local rules: You can check if the file "d:/agentic/.agents/AGENTS.md" exists to read project-specific coding guidelines.
- Custom skills: You can search and read matched skills in the directory "d:/agentic/.agents/skills/".
Use the standard "read_file" tool to read these files if you think they are relevant to your task.

### Iterative ReAct Workflow:
1. Locate: Use grep_search or list_dir to find files.
2. Read: Use read_file to inspect target files.
3. Edit: Use patch_file to write precise code edits.
4. Verify: Run compiler/tests or terminal commands using your execution tools.
5. Correct: If tests fail or errors occur, analyze the trace and edit again.
6. Complete: When you have successfully completed the task, output a clear summary of your changes and output, stating that the task is completed."""

    llm = LLMCaller()
    converted = convert_messages(state["messages"])
    
    # Expose tools
    tool_schemas = list(NATIVE_SKILLS_SCHEMAS)
    from agentcore.mcps import get_all_mcps, get_mcp_tool_schemas
    for mcp_name, mcp_class in get_all_mcps().items():
        if mcp_name == "filesystem-mcp":
            continue
        instance = mcp_class()
        tool_schemas.extend(get_mcp_tool_schemas(instance))
        
    from agentcore.mcp import get_mcp_manager
    manager = get_mcp_manager()
    for client_name, client in manager._clients.items():
        if client.status == "healthy":
            for tool in client.tools:
                tool_schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", tool["name"]),
                        "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
                    }
                })
                
    # Prune historical messages to stay within context windows for weak models
    if len(converted) > 15:
        system_msg = {"role": "system", "content": SYSTEM_PROMPT}
        converted = [system_msg] + converted[-14:]
    else:
        system_msg = {"role": "system", "content": SYSTEM_PROMPT}
        converted = [system_msg] + [m for m in converted if m.get("role") != "system"]
        
    tokens = []
    reasonings = []
    tool_calls = []
    
    async for chunk in llm.call(
        converted,
        tools=tool_schemas,
        stream=True,
        context=context
    ):
        if chunk["type"] == "reasoning":
            if callback:
                await callback({"type": "reasoning", "text": chunk["text"]})
            reasonings.append(chunk["text"])
        elif chunk["type"] == "token":
            if callback:
                await callback({"type": "token", "text": chunk["text"]})
            tokens.append(chunk["text"])
        elif chunk["type"] == "tool_calls":
            tool_calls = chunk["calls"]
            tokens.append(chunk["content"])
            
    assistant_text = "".join(tokens)
    reasoning_text = "".join(reasonings) if reasonings else None
    
    if not tool_calls and assistant_text:
        from agentcore.loop.agents import parse_text_tool_call
        parsed = parse_text_tool_call(assistant_text)
        if parsed:
            tool_calls = [{
                "id": "call_" + uuid.uuid4().hex[:8],
                "type": "function",
                "function": {"name": parsed["name"], "arguments": json.dumps(parsed["arguments"])}
            }]
            assistant_text = ""
            
    langchain_tool_calls = []
    for tc in tool_calls:
        try:
            args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
        except Exception:
            args = {}
        langchain_tool_calls.append({
            "name": tc["function"]["name"],
            "args": args,
            "id": tc["id"],
            "type": "tool_call"
        })
        
    ai_msg = AIMessage(content=assistant_text, tool_calls=langchain_tool_calls)
    if not langchain_tool_calls and callback:
        await callback({"type": "completed", "content": assistant_text})
        
    # Save the assistant message in database
    async with get_db_manager().session() as db:
        db_tool_calls = []
        for tc in tool_calls:
            db_tool_calls.append({
                "id": tc["id"],
                "type": tc.get("type", "function"),
                "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
            })
        db_msg = MessageModel(
            session_id=session_id,
            task_id=task_id,
            role="assistant",
            content=assistant_text,
            reasoning=reasoning_text,
            tool_calls=db_tool_calls if db_tool_calls else None
        )
        db.add(db_msg)
        await db.commit()
        
    # Mark task done if finished
    if not langchain_tool_calls:
        for t in tasks:
            if t["id"] == active_id:
                t["status"] = "done"
                t["output"] = assistant_text
                
    return {
        "messages": [ai_msg],
        "tasks": tasks,
        "active_issue_id": active_id,
        "step_count": steps
    }

# =============================================================================
# ROUTING EDGES
# =============================================================================

def route_after_classifier(state: AgentState) -> str:
    if state["route"] in ("CONVERSATION", "INSPECT"):
        return "direct_agent"
    return "crew_planner"

def route_after_direct_agent(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_executor"
    return END

def route_after_crew_planner(state: AgentState) -> str:
    return "dynamic_worker"

def route_after_dynamic_worker(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_executor"
        
    # Check if there are any remaining todo tasks
    tasks = state.get("tasks", [])
    next_task = next((t for t in tasks if t.get("status") == "todo"), None)
    if next_task:
        return "dynamic_worker"
        
    return END

def route_after_tool_executor(state: AgentState) -> str:
    if state["route"] in ("CONVERSATION", "INSPECT"):
        return "direct_agent"
    return "dynamic_worker"

# =============================================================================
# GRAPH COMPILATION
# =============================================================================

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("classify_input", classify_input_node)
workflow.add_node("direct_agent", direct_agent_node)
workflow.add_node("tool_executor", tool_executor_node)
workflow.add_node("crew_planner", crew_planner_node)
workflow.add_node("dynamic_worker", dynamic_worker_node)

# Add Edges
workflow.add_edge(START, "classify_input")

workflow.add_conditional_edges(
    "classify_input",
    route_after_classifier,
    {
        "direct_agent": "direct_agent",
        "crew_planner": "crew_planner"
    }
)

workflow.add_conditional_edges(
    "direct_agent",
    route_after_direct_agent,
    {
        "tool_executor": "tool_executor",
        END: END
    }
)

workflow.add_edge("crew_planner", "dynamic_worker")

workflow.add_conditional_edges(
    "dynamic_worker",
    route_after_dynamic_worker,
    {
        "tool_executor": "tool_executor",
        "dynamic_worker": "dynamic_worker",
        END: END
    }
)

workflow.add_conditional_edges(
    "tool_executor",
    route_after_tool_executor,
    {
        "direct_agent": "direct_agent",
        "dynamic_worker": "dynamic_worker"
    }
)

# Custom Redis Saver Checkpointer
memory = AsyncRedisSaver()
compiled_graph = workflow.compile(checkpointer=memory)

def get_compiled_graph(checkpointer) -> Any:
    """Compile the graph with a custom checkpointer."""
    return workflow.compile(checkpointer=checkpointer)

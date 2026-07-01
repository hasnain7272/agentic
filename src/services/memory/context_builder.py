"""
Context Builder Service

Assembles the LLM's message history from the database.
Core dependency of the BrainWorker.
"""
import logging
import os
import platform
import datetime
import json
from typing import List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.message_model import MessageModel
from src.services.memory.vector_store import get_semantic_graph

logger = logging.getLogger(__name__)


def get_dynamic_system_prompt(session=None, semantic_context: str = "") -> str:
    """Generates a highly-contextualized persona prompt with environment-aware boundaries."""
    os_name = platform.system()
    cwd = os.getcwd()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check for sandbox mode (env set by DockerAdapter)
    sandbox_mode = os.environ.get("SANDBOX_MODE", "DOCKER" if os.environ.get("DOCKER_IMAGE") else "LOCAL")

    # Dynamically pull exact tool names from registry
    from src.tools.registry import get_tool_names
    available_tools = get_tool_names()
    tool_list = ", ".join(f'`{t}`' for t in available_tools) if available_tools else "`bash_execute`, `read_file`, `write_file`"
    
    return f"""You are the Lead Orchestrator of the **project_kernel_runtime**, a production-grade agentic SaaS platform.
You operate as a senior software engineering manager within a secure, isolated sandbox: {sandbox_mode}.
Your job is to break down complex problems and delegate them to specialized sub-agents using the `delegate_task` tool, or solve them directly if they are simple.

[ENVIRONMENT]
- Host OS: {os_name}
- Sandbox: {sandbox_mode}
- Base Directory: {cwd}
- System Time: {now}
- Working Directory: /workspace (isolated session workspace)
{f"- Mounted Folders: {', '.join(session.mounted_folders)}" if session and session.mounted_folders else ""}

[WORKSPACE TOPOLOGY]
- `/workspace`: Your primary home. Files uploaded from the UI appear here.
- `/workspace/repos`: Sub-folders for any Git repositories you clone.
- `/workspace/persistent`: A folder for files that should survive the current session (conceptually).

[SEMANTIC ARCHIVAL MEMORY]
You have access to a long-term vector database of your past experiences and decisions via the `search_past_decisions` tool. If you are unsure of how you implemented a feature previously or need past context, you MUST use this tool to query your memory.

[AVAILABLE TOOLS]
You have EXACTLY these tools: {tool_list}
DO NOT invent or guess tool names.

[RULES OF ENGAGEMENT]
1. **Agentic Decision-Making**: There are ZERO hardcoded paths for results. YOU decide where files go based on the user's intent.
2. **Discussion-First**: Before performing any permanent output (like `git_commit` or moving files to a persistent folder), DISCUSS your plan with the user.
3. **Sandbox Hygiene**: Treat `/workspace` as your playground. Clean up temporary files before finishing.
4. **Output Dispatch**: When the task is complete, use the `dispatch_output` tool to summarize where you placed the results (Git, local workspace, or sandbox for download).
5. **Adaptive Reasoning**: If you can't find a file, don't give up. Use `bash_execute` with `find` or `ls -R` to search the `/workspace` topology.
"""


async def build_llm_context(
    db: AsyncSession,
    session_id: str,
    task_id: str | None = None,
    max_turns: int = 40,
    session: Any = None,
) -> List[Dict[str, str]]:
    """
    Pulls the last N conversation turns from the database
    and prepends the system prompt.

    If session is not provided, it will be loaded (without tenant filter for backward compatibility).
    """
    # Fetch the session for memory / mounted folders / tenant context
    from src.infrastructure.db.models.session_model import SessionModel
    if session is None:
        session_result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
        session = session_result.scalar_one_or_none()
    tenant_id = session.tenant_id if session else None

    conditions = [MessageModel.session_id == session_id]
    if tenant_id:
        conditions.append(MessageModel.tenant_id == tenant_id)
    if task_id:
        conditions.append(MessageModel.task_id == task_id)

    stmt = (
        select(MessageModel)
        .where(*conditions)
        .order_by(MessageModel.sequence.asc())
        .limit(max_turns)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Identify the last user message to use as a semantic query
    last_user_query = ""
    for row in reversed(rows):
        if row.role == "user" and row.content:
            last_user_query = row.content
            break
            
    # Retrieve AST semantic context
    semantic_snippets = ""
    if last_user_query:
        graph = get_semantic_graph()
        chunks = await graph.retrieve_context(session_id, last_user_query)
        for chunk in chunks:
            semantic_snippets += f"\n--- File: {chunk['file']} ---\n{chunk['content']}\n"

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": get_dynamic_system_prompt(session, semantic_snippets)}
    ]

    MAX_CHARS = 15000

    for row in rows:
        raw_content = row.content or ""

        if len(raw_content) > MAX_CHARS and row.role in ["tool", "assistant"]:
            cache_dir = os.path.abspath(os.path.join(os.getcwd(), "workspace", ".sandbox_cache"))
            os.makedirs(cache_dir, exist_ok=True)
            dump_path = os.path.join(cache_dir, f"context_dump_{row.id}.txt")

            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(raw_content)

            head = raw_content[:5000]
            tail = raw_content[-5000:]
            clipped = len(raw_content) - 10000

            compacted_content = (
                f"{head}\n\n"
                f"...[{clipped} BYTES COMPACTED (SWE-Agent Strict Bounds)]...\n"
                f"[Full output paged to MemGPT Archival Disk: {dump_path}]\n\n"
                f"{tail}\n"
            )
            entry: Dict[str, str] = {"role": row.role, "content": compacted_content}
        else:
            entry: Dict[str, str] = {"role": row.role, "content": raw_content}

        if row.tool_call_id:
            entry["tool_call_id"] = row.tool_call_id
            
        if row.tool_calls:
            try:
                entry["tool_calls"] = json.loads(row.tool_calls) if isinstance(row.tool_calls, str) else row.tool_calls
            except:
                pass
                
        if row.extra_metadata:
            entry["metadata"] = row.extra_metadata
            
        messages.append(entry)

    return messages


async def persist_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    task_id: str | None = None,
    tool_call_id: str | None = None,
    tool_calls: list | None = None,
    metadata: dict | None = None,
) -> MessageModel:
    """Write a single conversation turn to the database."""
    from src.infrastructure.db.models.session_model import SessionModel
    from src.infrastructure.db.session import _is_postgres

    # Row-level locking for sequence safety — only on PostgreSQL.
    # SQLite serializes writes at the engine level; with_for_update()
    # would escalate to an exclusive DB lock and cause "database is locked".
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    if _is_postgres:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    tenant_id = session.tenant_id if session else "local"

    max_stmt = select(func.coalesce(func.max(MessageModel.sequence), -1)).where(MessageModel.session_id == session_id)
    if tenant_id:
        max_stmt = max_stmt.where(MessageModel.tenant_id == tenant_id)
    result = await db.execute(max_stmt)
    next_seq = (result.scalar() or -1) + 1

    msg = MessageModel(
        tenant_id=tenant_id,
        session_id=session_id,
        task_id=task_id,
        role=role,
        content=content,
        tool_call_id=tool_call_id,
        tool_calls=json.dumps(tool_calls) if tool_calls else None,
        extra_metadata=metadata or {},
        sequence=next_seq,
    )
    db.add(msg)
    await db.flush()
    return msg


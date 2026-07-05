import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, and_, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import secrets
from pathlib import Path

from agentcore.config import get_settings
from agentcore.database import *
from agentcore.auth import *
from agentcore.schema import *
from agentcore.utils import *
from agentcore.governance import get_governance_engine
from agentcore.tools import get_tool_registry

logger = logging.getLogger(__name__)
settings = get_settings()


chat_router = APIRouter(prefix="/chat", tags=["chat"])

class ChatCreateRequest(BaseModel):
    session_id: str
    message: str
    shadow_mode: Optional[bool] = False
    active_model_id: Optional[str] = None

@chat_router.post("/")
async def create_chat_message(
    req: ChatCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session access
    result = await db.execute(
        select(SessionModel).where(
            and_(SessionModel.id == req.session_id, SessionModel.tenant_id == user.tenant_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # If the user passed active_model_id, update it on the session
    if req.active_model_id:
        session.active_model_id = req.active_model_id
        db.add(session)
        await db.flush()

    # Create task
    task = TaskModel(
        tenant_id=user.tenant_id,
        session_id=req.session_id,
        description=req.message,
        status="pending",
    )
    db.add(task)
    await db.flush()

    # Add the user's message to the database
    from agentcore.database import add_message
    await add_message(db, req.session_id, "user", req.message, task.id)
    await db.commit()

    # Agentic-driven session naming: if session has default timestamp name, generate from first message
    if session.title and session.title.startswith("Session ") and len(session.title) > 8:
        # Check if this is the first user message in this session
        msg_count = await db.execute(
            select(MessageModel).where(MessageModel.session_id == req.session_id, MessageModel.role == "user")
        )
        user_msgs = msg_count.scalars().all()
        if len(user_msgs) == 1:
            # Generate a meaningful name from the first message
            new_name = await _generate_session_name(req.message)
            if new_name:
                session.title = new_name
                db.add(session)
                await db.commit()

    return {"task_id": task.id}


async def _generate_session_name(first_message: str) -> str:
    """Generate a concise session name from the first user message using LLM."""
    try:
        from agentcore.config import get_settings
        from litellm import acompletion
        
        settings = get_settings()
        raw_key = settings.llm_api_key
        base_url = settings.llm_base_url
        model = settings.llm_model
        
        if not raw_key:
            return _fallback_session_name(first_message)
        
        prompt = f"""Generate a concise, descriptive session name (max 5 words) for this user task:
        
User message: "{first_message}"

Return ONLY the session name, no quotes, no explanation. Examples:
- "Fix login authentication bug"
- "Build REST API for users"
- "Refactor database models"
- "Add dark mode toggle"
- "Deploy to Kubernetes"
"""
        
        completion_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 30,
        }
        if base_url:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=base_url, api_key=raw_key)
            response = await client.chat.completions.create(**completion_kwargs)
        else:
            completion_kwargs["api_key"] = raw_key
            if "/" in model:
                completion_kwargs["custom_llm_provider"] = model.split("/")[0]
            else:
                completion_kwargs["custom_llm_provider"] = "openai"
            response = await acompletion(**completion_kwargs)
        
        name = response.choices[0].message.content.strip()
        # Clean up the name
        name = name.strip('"\'').strip()
        if len(name) > 60:
            name = name[:57] + "..."
        return name if name else _fallback_session_name(first_message)
    except Exception as e:
        logger.error(f"Failed to generate session name: {e}")
        return _fallback_session_name(first_message)


def _fallback_session_name(message: str) -> str:
    """Generate a fallback session name from message without LLM."""
    # Extract key phrases - first sentence or first 50 chars
    msg = message.strip()
    if not msg:
        return "New Session"
    
    # Try to get first sentence
    import re
    sentences = re.split(r'[.!?]+', msg)
    first_sentence = sentences[0].strip() if sentences else msg
    
    # If too long, truncate
    if len(first_sentence) > 50:
        first_sentence = first_sentence[:47] + "..."
    
    # Capitalize first letter
    if first_sentence:
        first_sentence = first_sentence[0].upper() + first_sentence[1:]
    
    return first_sentence or "New Session"

@chat_router.get("/{session_id}/history")
async def get_chat_history(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session access
    result = await db.execute(
        select(SessionModel).where(
            and_(SessionModel.id == session_id, SessionModel.tenant_id == user.tenant_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # Retrieve history
    msgs_result = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at)
    )
    messages = []
    for m in msgs_result.scalars().all():
        messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else datetime.utcnow().isoformat(),
        })

    return {"messages": messages}

@chat_router.post("/{session_id}/approve")
async def approve_chat_tool(
    session_id: str,
    req: Dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg_id = req.get("message_id")
    decision = req.get("decision")

    # 1. Look up by Message ID first
    msg_res = await db.execute(
        select(MessageModel).where(MessageModel.id == msg_id)
    )
    msg = msg_res.scalar_one_or_none()

    approval_id = None
    if msg and msg.meta:
        approval_id = msg.meta.get("approval_id")

    if not approval_id:
        # Fallback to direct approval_id lookup
        approval_id = msg_id

    result = await db.execute(
        select(ApprovalModel).where(
            ApprovalModel.id == approval_id,
            ApprovalModel.tenant_id == user.tenant_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Approval not found")

    approval.status = "approved" if decision == "approved" else "rejected"
    approval.approver_id = user.user_id
    approval.approved_at = datetime.utcnow()

    # 2. Update ToolCallModel status
    if approval.context and "tool_call_id" in approval.context:
        tc_id = approval.context["tool_call_id"]
        tc_res = await db.execute(select(ToolCallModel).where(ToolCallModel.id == tc_id))
        tc = tc_res.scalar_one_or_none()
        if tc:
            tc.status = "approved" if decision == "approved" else "rejected"
            db.add(tc)

    # 3. Update message meta status so UI updates StatusMark
    if msg:
        meta = dict(msg.meta or {})
        meta["status"] = "APPROVED" if decision == "approved" else "DENIED"
        msg.meta = meta
        db.add(msg)

    # 4. If denied, add a tool rejection message to the DB so the LLM gets it
    if decision == "denied":
        tool_call_id = approval.context.get("tool_call_id") if approval.context else None
        from agentcore.database import add_message
        await add_message(
            db,
            session_id=session_id,
            role="tool",
            content="Tool execution denied by user.",
            task_id=msg.task_id if msg else None,
            tool_call_id=tool_call_id
        )

    await db.commit()
    return {"status": approval.status}

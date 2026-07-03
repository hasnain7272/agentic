import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from litellm import acompletion
from openai import AsyncOpenAI
from sqlalchemy import select

from agentcore.config import get_settings
from agentcore.tools import get_tool_registry, get_tool_handler, get_all_tool_schemas
from agentcore.governance import get_governance_engine, GovernanceApprovalRequiredError
from agentcore.database import (
    get_db, get_db_manager, create_session, create_task, add_message, add_tool_call,
    update_tool_call, TaskModel, TaskStatus, MessageModel, ToolCallModel, SessionModel, UserModel
)
from agentcore.auth import TokenPayload

logger = logging.getLogger(__name__)
settings = get_settings()

from .state import AgentState, AgentContext

class LLMCaller:
    def __init__(self):
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5

    async def call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        stream: bool = True,
        context: Optional[AgentContext] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        settings = get_settings()
        raw_key = settings.llm_api_key
        base_url = settings.llm_base_url
        model = settings.llm_model
        temperature = settings.llm_temperature
        max_tokens = settings.llm_max_tokens

        # 1. Check for session-level BYOK config (highest priority)
        if context and context.session_id:
            from sqlalchemy import select
            from agentcore.database import SessionModel
            async with get_db_manager().session() as db:
                try:
                    s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                    session = s_res.scalar_one_or_none()
                    if session and session.meta:
                        byok_config = session.meta.get("byok_config")
                        if byok_config and byok_config.get("api_key"):
                            raw_key = byok_config.get("api_key")
                            if byok_config.get("model"):
                                model = byok_config.get("model")
                            if byok_config.get("base_url") is not None:
                                base_url = byok_config.get("base_url")
                            if byok_config.get("temperature") is not None:
                                temperature = float(byok_config.get("temperature"))
                            if byok_config.get("max_tokens") is not None:
                                max_tokens = int(byok_config.get("max_tokens"))
                            logger.info(f"Using session-level BYOK config for session {context.session_id}")
                except Exception as e:
                    logger.error(f"Failed to load session-level BYOK config: {e}")

        # 2. Check for user-level BYOM config (fallback)
        if context and context.tenant_id:
            from sqlalchemy import select
            from agentcore.database import UserModel, SessionModel
            async with get_db_manager().session() as db:
                try:
                    u_res = await db.execute(select(UserModel).where(UserModel.id == context.user_id))
                    db_user = u_res.scalar_one_or_none()
                    if db_user and db_user.settings:
                        byom_configs = db_user.settings.get("byom_configs", [])
                        if byom_configs:
                            selected = byom_configs[0]
                            s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                            session = s_res.scalar_one_or_none()
                            if session and session.active_model_id:
                                for cfg in byom_configs:
                                    if cfg.get("id") == session.active_model_id:
                                        selected = cfg
                                        break
                            if selected:
                                if selected.get("api_key"):
                                    raw_key = selected.get("api_key")
                                if selected.get("model"):
                                    model = selected.get("model")
                                if selected.get("base_url") is not None:
                                    base_url = selected.get("base_url")
                                if selected.get("temperature") is not None:
                                    temperature = float(selected.get("temperature"))
                                if selected.get("max_tokens") is not None:
                                    max_tokens = int(selected.get("max_tokens"))
                except Exception as e:
                    logger.error(f"Failed to load dynamic BYOM config: {e}")

        if not raw_key:
            yield {"type": "error", "error": "No API key configured. Please enter your API key in settings."}
            return

        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if settings.llm_top_p:
            completion_kwargs["top_p"] = settings.llm_top_p
        if max_tokens:
            completion_kwargs["max_tokens"] = max_tokens
        if tools:
            completion_kwargs["tools"] = tools
            completion_kwargs["tool_choice"] = "auto"

        max_attempts = 4
        for attempt in range(max_attempts):
            yielded_any_content = False
            try:
                if base_url:
                    client = AsyncOpenAI(base_url=base_url, api_key=raw_key)
                    response = await client.chat.completions.create(**completion_kwargs)
                else:
                    completion_kwargs["api_key"] = raw_key
                    if "/" in model:
                        completion_kwargs["custom_llm_provider"] = model.split("/")[0]
                    else:
                        completion_kwargs["custom_llm_provider"] = "openai"
                    response = await acompletion(**completion_kwargs)
                
                self._circuit_breaker_failures = 0
                tool_calls_dict = {}
                collected_content = []

                async for chunk in response:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices or getattr(choices[0], "delta", None) is None:
                        continue
                    delta = choices[0].delta

                    if getattr(delta, "reasoning_content", None):
                        yielded_any_content = True
                        yield {"type": "reasoning", "text": delta.reasoning_content}

                    if delta.content:
                        yielded_any_content = True
                        collected_content.append(delta.content)
                        yield {"type": "token", "text": delta.content}

                    if delta.tool_calls:
                        yielded_any_content = True
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_dict:
                                tool_calls_dict[idx] = {"id": tc.id, "type": tc.type, "function": {"name": "", "arguments": ""}}
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_dict[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments

                # Yield final aggregated result
                if tool_calls_dict:
                    combined_calls = list(tool_calls_dict.values())
                    yield {"type": "tool_calls", "calls": combined_calls, "content": "".join(collected_content)}
                else:
                    yield {"type": "message", "content": "".join(collected_content)}
                
                # Successful execution, break the retry loop
                break

            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = any(x in err_str for x in ["resourceexhausted", "rate limit", "429", "worker local total request limit"])
                if is_rate_limit and attempt < max_attempts - 1 and not yielded_any_content:
                    wait_time = 2 ** attempt
                    logger.warning(f"LLM call rate limited/exhausted ({e}). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(wait_time)
                    continue
                
                logger.error(f"LLM call/stream failed: {e}")
                yield {"type": "error", "error": f"LLM error: {e}"}
                return

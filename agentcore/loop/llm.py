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

    async def _get_model_config(self, target_model_id: str, context: Optional[AgentContext]) -> tuple:
        settings = get_settings()
        raw_key = settings.llm_api_key
        base_url = settings.llm_base_url
        model = target_model_id
        temperature = settings.llm_temperature
        max_tokens = settings.llm_max_tokens
        provider = "openai"

        if context and context.session_id:
            async with get_db_manager().session() as db:
                try:
                    s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                    session = s_res.scalar_one_or_none()
                    if session and session.meta:
                        byok_config = session.meta.get("byok_config")
                        if byok_config and byok_config.get("model") == target_model_id:
                            if byok_config.get("api_key"):
                                raw_key = byok_config.get("api_key")
                            if byok_config.get("model"):
                                model = byok_config.get("model")
                            if byok_config.get("base_url") is not None:
                                base_url = byok_config.get("base_url")
                            if byok_config.get("temperature") is not None:
                                temperature = float(byok_config.get("temperature"))
                            if byok_config.get("max_tokens") is not None:
                                max_tokens = int(byok_config.get("max_tokens"))
                            if byok_config.get("provider"):
                                provider = byok_config.get("provider")
                except Exception as e:
                    logger.error(f"Failed to load session BYOK for {target_model_id}: {e}")

        if context and context.tenant_id:
            async with get_db_manager().session() as db:
                try:
                    u_res = await db.execute(select(UserModel).where(UserModel.id == context.user_id))
                    db_user = u_res.scalar_one_or_none()
                    if db_user and db_user.settings:
                        byom_configs = db_user.settings.get("byom_configs", [])
                        selected = None
                        for cfg in byom_configs:
                            if cfg.get("id") == target_model_id:
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
                            if selected.get("provider"):
                                provider = selected.get("provider")
                except Exception as e:
                    logger.error(f"Failed to load user BYOM for {target_model_id}: {e}")

        # Clean and sanitize configuration dynamically
        if model:
            model = model.strip()
            # De-duplicate doubled model names (e.g. name + name)
            if len(model) % 2 == 0:
                half = len(model) // 2
                if model[:half] == model[half:]:
                    model = model[:half]
            # Remove duplicate consecutive slashes/prefixes (e.g. ollama/ollama/model)
            parts = model.split("/")
            unique_parts = []
            for p in parts:
                if not unique_parts or unique_parts[-1] != p:
                    unique_parts.append(p)
            model = "/".join(unique_parts)

        if provider:
            provider = provider.strip()
        if base_url:
            base_url = base_url.strip()

        if not raw_key and base_url:
            raw_key = "local"
        return raw_key, base_url, model, temperature, max_tokens, provider

    async def call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        stream: bool = True,
        context: Optional[AgentContext] = None,
        is_worker: bool = False,
        model_override: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # 1. Resolve priority chain list or apply override
        priorities = []
        if model_override:
            priorities = [model_override]
        else:
            if context and context.session_id:
                async with get_db_manager().session() as db:
                    try:
                        s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                        session = s_res.scalar_one_or_none()
                        if session and session.meta:
                            priorities = session.meta.get("model_priorities", [])
                    except Exception as e:
                        logger.error(f"Failed to load model priorities: {e}")

            # Fallback to active model ID if no priority list is configured
            if not priorities:
                settings = get_settings()
                fallback_model = settings.llm_model
                if context and context.session_id:
                    async with get_db_manager().session() as db:
                        try:
                            s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                            session = s_res.scalar_one_or_none()
                            if session and session.active_model_id:
                                fallback_model = session.active_model_id
                        except Exception:
                            pass
                priorities = [fallback_model]

        # Always append default system model as ultimate fallback if not already present
        settings = get_settings()
        default_system_model = settings.llm_model
        if default_system_model not in priorities:
            priorities.append(default_system_model)

        # Iterate through priorities in sequence to find a working model
        last_error = None
        successful_model = None
        draft_content = ""
        draft_calls = []

        for target_model_id in priorities:
            raw_key, base_url, model, temperature, max_tokens, provider = await self._get_model_config(target_model_id, context)

            prov_lower = provider.lower() if provider else "openai"
            if prov_lower == "ollama":
                if not model.startswith("ollama/"):
                    model = f"ollama/{model}"
                if base_url:
                    base_url = base_url.replace("/v1", "").rstrip("/")
            else:
                if base_url and not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                    if "/v1" not in base_url:
                        base_url = base_url.rstrip("/") + "/v1"

            if not raw_key:
                if base_url:
                    raw_key = "local"
                else:
                    last_error = f"No API key configured for model {target_model_id}."
                    logger.warning(f"Skipping model {target_model_id} due to missing API key.")
                    yield {"type": "token", "text": f"\n\n> [!WARNING]\n> **Swarm Warning:** Model `{target_model_id}` skipped (no API key configured). Trying next model...\n\n"}
                    continue

            completion_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
                "api_key": raw_key,
            }
            if base_url:
                completion_kwargs["api_base"] = base_url
            
            if "/" in model:
                completion_kwargs["custom_llm_provider"] = model.split("/")[0]
            else:
                completion_kwargs["custom_llm_provider"] = prov_lower

            settings = get_settings()
            if settings.llm_top_p:
                completion_kwargs["top_p"] = settings.llm_top_p
            if max_tokens:
                completion_kwargs["max_tokens"] = max_tokens
            if tools:
                completion_kwargs["tools"] = tools
                completion_kwargs["tool_choice"] = "auto"

            max_attempts = 4
            yielded_any_content = False
            model_success = False

            for attempt in range(max_attempts):
                try:
                    response = await acompletion(**completion_kwargs)

                    self._circuit_breaker_failures = 0
                    tool_calls_dict = {}
                    collected_content = []

                    if hasattr(response, "__aiter__"):
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
                    else:
                        # Non-streaming response ModelResponse
                        choices = getattr(response, "choices", None) or []
                        if choices:
                            message = choices[0].message
                            if getattr(message, "reasoning_content", None):
                                yielded_any_content = True
                                yield {"type": "reasoning", "text": message.reasoning_content}
                            if message.content:
                                yielded_any_content = True
                                collected_content.append(message.content)
                                yield {"type": "token", "text": message.content}
                            if getattr(message, "tool_calls", None):
                                yielded_any_content = True
                                for idx, tc in enumerate(message.tool_calls):
                                    tool_calls_dict[idx] = {
                                        "id": tc.id,
                                        "type": tc.type,
                                        "function": {
                                            "name": tc.function.name,
                                            "arguments": tc.function.arguments
                                        }
                                    }

                    draft_content = "".join(collected_content)
                    draft_calls = list(tool_calls_dict.values())
                    model_success = True
                    break

                except Exception as attempt_err:
                    err_str = str(attempt_err).lower()
                    is_rate_limit = any(x in err_str for x in ["resourceexhausted", "rate limit", "429", "worker local total request limit"])
                    if is_rate_limit and attempt < max_attempts - 1 and not yielded_any_content:
                        wait_time = 2 ** attempt
                        logger.warning(f"LLM call rate limited/exhausted ({attempt_err}). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_attempts})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if yielded_any_content:
                        logger.error(f"LLM call failed midway after yielding tokens: {attempt_err}")
                        yield {"type": "error", "error": f"LLM stream error: {attempt_err}"}
                        return
                    
                    last_error = f"Model {target_model_id} failed: {attempt_err}"
                    break

            if model_success:
                successful_model = target_model_id
                break
            else:
                logger.warning(f"Swarm model {target_model_id} failed: {last_error}. Cascading to next model in team...")
                yield {"type": "token", "text": f"\n\n> [!WARNING]\n> **Swarm Warning:** Model `{target_model_id}` failed: {last_error}. Cascading to next model...\n\n"}
                continue

        # If all models in the priority list failed:
        if not successful_model:
            yield {"type": "error", "error": f"All models in priorities list failed. Last error: {last_error}"}
            return

        # A2A Team Swarm Action Refinement: Let remaining reviewer models refine reasoning and tool calls
        # Bypassed in PGE single-agent flat direct loop for maximum speed and efficiency.
        pass

        # Yield final aggregated/refined result
        if draft_calls:
            yield {"type": "tool_calls", "calls": draft_calls, "content": draft_content}
        else:
            yield {"type": "message", "content": draft_content}

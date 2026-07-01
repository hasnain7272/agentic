"""LLM Execution logic for brain."""
import logging
from typing import Dict, Any, List

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.services.memory.context_builder import persist_message
from src.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

async def call_llm_and_stream(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    task_id: str,
    trace_id: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    llm_config: Dict[str, Any],
    circuit_breaker: CircuitBreaker
) -> None:
    """Execute LLM and stream results."""
    broker = await get_streams_broker()
    raw_key = llm_config.get("api_key", "")

    if not raw_key:
        error_msg = (
            "\x1b[38;5;196m[CONFIG ERROR]\x1b[0m No API key configured.\r\n"
            "Click the ⚙ Settings icon to configure your LLM provider.\r\n"
        )
        await broker.publish(f"task_log:{task_id}", error_msg.encode("utf-8"))
        await persist_message(db, session_id, "assistant", "⚠️ No API key configured.", task_id=task_id)
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
        await db.commit()
        return

    completion_kwargs: Dict[str, Any] = {
        "model": llm_config["model"],
        "messages": messages,
        "temperature": llm_config.get("temperature", 0.2),
        "stream": True,
    }
    if llm_config.get("top_p") is not None:
        completion_kwargs["top_p"] = llm_config["top_p"]
    if llm_config.get("max_tokens") is not None:
        completion_kwargs["max_tokens"] = llm_config["max_tokens"]
    if tools:
        completion_kwargs["tools"] = tools

    if llm_config.get("extra_body"):
        completion_kwargs["extra_body"] = llm_config["extra_body"]

    logger.info(f"[Brain] LLM config -> model={llm_config['model']}")
    await broker.publish(f"task_log:{task_id}", {"status": "thinking", "message": "Generating..."})

    try:
        if llm_config.get("base_url"):
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=llm_config["base_url"],
                api_key=raw_key
            )

            @circuit_breaker.protected
            async def _call_openai():
                return await client.chat.completions.create(**completion_kwargs)

            response = await _call_openai()
        else:
            completion_kwargs["api_key"] = raw_key
            if "/" in llm_config["model"]:
                completion_kwargs["custom_llm_provider"] = llm_config["model"].split("/")[0]
            else:
                completion_kwargs["custom_llm_provider"] = "openai"

            @circuit_breaker.protected
            async def _call_litellm():
                return await acompletion(**completion_kwargs)

            response = await _call_litellm()
    except CircuitBreakerOpenError:
        error_msg = "\x1b[38;5;196m[CIRCUIT BREAKER OPEN]\x1b[0m LLM service temporarily unavailable."
        await broker.publish(f"task_log:{task_id}", error_msg.encode("utf-8"))
        await persist_message(db, session_id, "assistant", error_msg, task_id=task_id)
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
        await db.commit()
        return
    except Exception as llm_err:
        error_text = str(llm_err)
        human_msg = f"⚠️ LLM Error: {error_text[:500]}"
        await broker.publish(f"task_log:{task_id}", f"\x1b[38;5;196m{human_msg}\x1b[0m\r\n".encode("utf-8"))
        await persist_message(db, session_id, "assistant", human_msg, task_id=task_id)
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
        await db.commit()
        return

    collected_content = []
    tool_calls_dict = {}

    model_label = llm_config["model"].split("/")[-1]
    await broker.publish(f"task_log:{task_id}", f"\x1b[38;5;46m[{model_label}] Thinking...\x1b[0m\r\n".encode("utf-8"))

    try:
        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            if not choices or getattr(choices[0], "delta", None) is None:
                continue
            delta = choices[0].delta
            if getattr(delta, "reasoning_content", None):
                await broker.publish(f"task_log:{task_id}", {"event": "reasoning", "text": delta.reasoning_content})
            if delta.content:
                collected_content.append(delta.content)
                await broker.publish(f"task_log:{task_id}", {"event": "token", "text": delta.content})
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {"id": tc.id, "type": tc.type, "function": {"name": "", "arguments": ""}}
                    if tc.function:
                        if tc.function.name:
                            tool_calls_dict[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments

        from src.services.agent_loop.brain.response_parser import process_response
        await process_response(db, session_id, tenant_id, task_id, trace_id, collected_content, tool_calls_dict)

    except Exception as stream_err:
        error_text = str(stream_err)
        human_msg = f"⚠️ LLM Streaming Error: {error_text[:500]}"
        await broker.publish(f"task_log:{task_id}", f"\r\n\x1b[38;5;196m{human_msg}\x1b[0m\r\n".encode("utf-8"))
        await persist_message(db, session_id, "assistant", human_msg, task_id=task_id)
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
        await db.commit()
        return

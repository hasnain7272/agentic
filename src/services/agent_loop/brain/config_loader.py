"""BYOK LLM config loading."""
import os
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.db.models.session_model import SessionModel
from src.infrastructure.security.crypto import decrypt_string


def _resolve_secret(raw_value: str) -> str:
    """Support encrypted keys while keeping legacy plaintext configs alive."""
    if not raw_value:
        return ""
    if raw_value.startswith("gAAAA"):
        return decrypt_string(raw_value)
    return raw_value

async def load_session_llm_config(db: AsyncSession, session_id: str, session: Any = None) -> Dict[str, Any]:
    """
    BYOK Resolution Order:
    1. SessionModel.context
    2. Environment variables
    """
    if session is None:
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
    ctx = (session.context if session else None) or {}

    # The requested model ID could be stored in session context or we default to the first BYOM config
    requested_model_id = ctx.get("active_model_id")

    tenant_id = None
    if session and hasattr(session, "tenant_id"):
        tenant_id = session.tenant_id

    api_key = ""
    model = "gpt-4o"
    base_url = ctx.get("base_url") or os.environ.get("LLM_BASE_URL")

    # Try fetching from Tenant's BYOM config
    found_in_byom = False
    if tenant_id:
        from src.infrastructure.db.models.tenant_model import TenantModel
        result = await db.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant and tenant.config:
            byom_configs = tenant.config.get("byom_configs", [])
            if byom_configs:
                selected = None
                if requested_model_id:
                    for b in byom_configs:
                        if b.get("id") == requested_model_id:
                            selected = b
                            found_in_byom = True
                            break
                
                # If requested model wasn't found in BYOM config, fall back to:
                # 1. The first BYOM config (if no specific model requested)
                # 2. Any BYOM config with an API key (if requested model wasn't in BYOM)
                if not found_in_byom:
                    if not requested_model_id:
                        selected = byom_configs[0]
                        found_in_byom = True
                    else:
                        # Requested model isn't in BYOM — try to find any config with a key
                        keyed = [b for b in byom_configs if b.get("api_key")]
                        if keyed:
                            selected = keyed[0]
                            found_in_byom = True
                    
                if selected:
                    api_key = _resolve_secret(selected.get("api_key", ""))
                    model = selected.get("model", "gpt-4o")
                    base_url = selected.get("base_url") or base_url
                    for key in ("temperature", "top_p", "max_tokens"):
                        if selected.get(key) is not None:
                            ctx[key] = selected[key]

    # If requested model is a known preset but not configured in the backend's BYOM config,
    # resolve default preset settings so that environment variables can be utilized.
    if not found_in_byom and requested_model_id:
        PRESET_DEFAULTS = {
            "nvidia-glm": {"model": "z-ai/glm-5.1", "base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY"},
            "nvidia-minimax": {"model": "minimaxai/minimax-m2.7", "base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY"},
            "nvidia-qwen-coder": {"model": "qwen/qwen3-coder-480b-a35b-instruct", "base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY"},
            "openai": {"model": "gpt-4o", "base_url": None, "key_env": "OPENAI_API_KEY"},
            "anthropic": {"model": "claude-sonnet-4-20250514", "base_url": None, "key_env": "ANTHROPIC_API_KEY"},
            "gemini": {"model": "gemini/gemini-2.5-pro", "base_url": None, "key_env": "GEMINI_API_KEY"},
            "ollama": {"model": "ollama/llama3.3", "base_url": "http://localhost:11434", "key_env": None},
        }
        preset = PRESET_DEFAULTS.get(requested_model_id)
        if preset:
            model = preset["model"]
            base_url = preset["base_url"] or base_url
            if preset["key_env"]:
                api_key = os.environ.get(preset["key_env"], "")

    config: Dict[str, Any] = {}
    config["model"] = (
        model
        or ctx.get("model")
        or os.environ.get("LLM_MODEL")
        or "nvidia/nemotron-3-super-120b-a12b"
    )

    config["api_key"] = (
        api_key
        or ctx.get("api_key")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("NVIDIA_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    )

    if base_url:
        config["base_url"] = base_url

    if ctx.get("temperature") is not None:
        config["temperature"] = float(ctx["temperature"])
    if ctx.get("top_p") is not None:
        config["top_p"] = float(ctx["top_p"])
    if ctx.get("max_tokens") is not None:
        config["max_tokens"] = int(ctx["max_tokens"])

    extra_body = ctx.get("extra_body")
    if extra_body and isinstance(extra_body, dict):
        config["extra_body"] = extra_body

    return config

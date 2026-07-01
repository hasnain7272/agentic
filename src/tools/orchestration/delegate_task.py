"""
Delegate Task Tool (Swarm Orchestrator)
Allows the lead agent to spawn a sub-agent with a specific persona.
"""
import json
import logging
import os
from typing import Any, Dict
from litellm import acompletion
from sqlalchemy import select

from src.tools.core.base import BaseTool, ToolParameter
from src.services.agent_loop.personas import get_persona_prompt
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.db.models.session_model import SessionModel
from src.tools.registry import get_all_tool_schemas, get_tool_instance

logger = logging.getLogger(__name__)

class DelegateTaskTool(BaseTool):
    name = "delegate_task"
    description = "Delegate a complex sub-task to a specialized agent. Wait for their result. Use this to divide and conquer."
    parameters = [
        ToolParameter(name="agent_role", type="string", description="Role: 'blender_expert', 'python_developer', 'security_auditor', 'devops_engineer'"),
        ToolParameter(name="task_description", type="string", description="Highly detailed instructions for what the sub-agent should do.")
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, agent_role: str, task_description: str, **kwargs) -> Dict[str, Any]:
        tenant_id = kwargs.get("tenant_id", "local")
        logger.info(f"[Swarm] Delegating to {agent_role}")
        
        async_session_factory = get_session_factory()
        async with async_session_factory() as db:
            result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found for delegation."}
            ctx = session.context or {}
            
            from src.infrastructure.security.crypto import decrypt_string
            enc_key = ctx.get("api_key")
            api_key = decrypt_string(enc_key) if enc_key else os.environ.get("OPENAI_API_KEY", "")
            model = ctx.get("model") or os.environ.get("LLM_MODEL") or "gpt-4o"
            base_url = ctx.get("base_url") or os.environ.get("LLM_BASE_URL")

        if not api_key:
            return {"error": "No API key configured for sub-agent."}

        persona_prompt = get_persona_prompt(agent_role)
        messages = [
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": f"Task: {task_description}\n\nYou can use tools to accomplish this. Do not ask for user input, just do the task and summarize the result."}
        ]
        
        tools = get_all_tool_schemas()
        
        iterations = 0
        while iterations < 5:
            iterations += 1
            
            completion_kwargs = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "temperature": 0.0,
                "api_key": api_key,
            }
            if base_url:
                completion_kwargs["api_base"] = base_url
                completion_kwargs["custom_llm_provider"] = "openai"

            try:
                response = await acompletion(**completion_kwargs)
            except Exception as e:
                return {"error": f"Sub-agent failed: {e}"}

            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))
            
            if not message.tool_calls:
                return {
                    "status": "success",
                    "agent": agent_role,
                    "result": message.content
                }
                
            for tc in message.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                tool_instance = get_tool_instance(tool_name)
                
                if tool_instance:
                    try:
                        from src.services.tool_execution.router import ToolExecutionRouter
                        router = ToolExecutionRouter()
                        mounted = session.mounted_folders if session else []
                        active_folder = mounted[0] if mounted else ""
                        tool_kwargs = {**tool_args, "folder_slug": active_folder}
                        
                        tool_result = await router.execute_tool(
                            tool_instance, session_id, tool_kwargs, tenant_id=tenant_id
                        )
                        output = json.dumps(tool_result, default=str)[:4000]
                    except Exception as e:
                        output = f"Error executing {tool_name}: {e}"
                else:
                    output = f"Tool {tool_name} not found."
                    
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": output
                })

        return {"error": "Sub-agent reached max iterations without returning final answer."}

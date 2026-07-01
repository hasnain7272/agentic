"""
Tool Execution Worker

Subscribes to `execution_queue`. When it receives an EXECUTE_TOOL
event, it runs the tool through the governance + sandbox pipeline,
persists the result, and re-publishes AGENT_THINK so the brain can
continue reasoning. This is the ReAct loop's second half.
"""
import json
import logging
from typing import Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.infrastructure.observability.tracing import traced
from src.infrastructure.db.models.session_model import SessionModel
from src.services.memory.context_builder import persist_message
from src.services.governance.policy_engine import PolicyEngine
from src.services.tool_execution.router import ToolExecutionRouter
from src.tools.registry import get_tool_instance

logger = logging.getLogger(__name__)


class ToolWorker:
    def __init__(self):
        self.router = ToolExecutionRouter()

    @traced("tool_worker.process_tool_event")
    async def process_tool_event(
        self, event: Dict[str, Any], db: AsyncSession
    ):
        task_id = event.get("task_id")
        session_id = event.get("session_id")
        trace_id = event.get("trace_id")
        tenant_id = event.get("tenant_id")
        tools = event.get("tools", [])
        if "tool" in event: # Backwards compatibility
            tools = [event["tool"]]
            
        broker = await get_streams_broker()

        # 1. Load session with tenant isolation
        if tenant_id:
            result = await db.execute(
                select(SessionModel).where(
                    and_(
                        SessionModel.id == session_id,
                        SessionModel.tenant_id == tenant_id,
                    )
                )
            )
        else:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
        session = result.scalar_one_or_none()
        if not session:
            logger.error(f"[ToolWorker] Session {session_id} not found or unauthorized (tenant={tenant_id})")
            output = f"ERROR: Session not found or unauthorized"
            await persist_message(db, session_id, "tool", output, task_id=task_id)
            await db.commit()
            await _re_trigger_brain(broker, task_id, session_id, trace_id, tenant_id)
            return

        any_approval_required = False
        
        for tool_spec in tools:
            tool_name = tool_spec.get("name", "")
            tool_args = tool_spec.get("args", {})
            tool_call_id = tool_spec.get("id")

            logger.info(f"[ToolWorker] Executing: {tool_name}")
            await broker.publish(f"task_log:{task_id}", {
                "event": "tool_executing",
                "name": tool_name,
                "message": f"Executing: {tool_name}..."
            })

            # 2. Governance check
            try:
                if session:
                    PolicyEngine.assert_action_allowed(
                        session, tool_name, tool_args
                    )
            except Exception as gov_err:
                from src.domain.exceptions import GovernanceApprovalRequiredError
                if isinstance(gov_err, GovernanceApprovalRequiredError):
                     logger.info(f"[Governance] HITL Approval required: {tool_name}")
                     await persist_message(
                        db, session_id, "tool",
                        f"APPROVAL REQUIRED: {gov_err}",
                        task_id=task_id,
                        tool_call_id=tool_call_id,
                        metadata={"status": "NEEDS_APPROVAL", "tool_name": tool_name, "args": tool_args}
                     )
                     any_approval_required = True
                else:
                    logger.warning(f"[Governance] Denied: {gov_err}")
                    await persist_message(
                        db, session_id, "tool",
                        f"GOVERNANCE DENIED: {gov_err}",
                        task_id=task_id,
                        tool_call_id=tool_call_id
                    )
                await db.commit()
                await broker.publish(f"task_log:{task_id}", {
                    "event": "tool_approval_required",
                    "name": tool_name
                })
                continue

            # 3. Execute through the sandboxed router
            tool_instance = get_tool_instance(tool_name)
            
            # Derive active workspace from mounted_folders (replaces legacy folder_slug)
            mounted = session.mounted_folders if session else []
            active_folder = mounted[0] if mounted else ""

            if not tool_instance:
                output = f"Unknown tool: {tool_name}"
                logger.error(output)
            elif tool_args.pop("dry_run", False) or session.context.get("shadow_mode", False):
                # --- Tool Shadowing / Dry-Run ---
                output = f"[SHADOW MODE] Simulated execution of '{tool_name}'. No real actions were taken. Args: {tool_args}"
                logger.info(output)
            else:
                try:
                    import asyncio
                    execution_kwargs = {**tool_args, "folder_slug": active_folder}
                    result = await asyncio.wait_for(
                        self.router.execute_tool(
                            tool_instance, session_id, execution_kwargs, tenant_id=tenant_id or "local"
                        ),
                        timeout=120.0
                    )
                    output = json.dumps(result, default=str)[:8000]
                except asyncio.TimeoutError:
                    output = f"TOOL ERROR: Execution timed out after 120 seconds. The tool took too long to complete."
                    logger.error(f"[ToolWorker] {output}")
                except Exception as exec_err:
                    output = f"TOOL ERROR: {exec_err}"
                    logger.error(f"[ToolWorker] {output}")

            # 4. Persist tool result as a message
            await persist_message(
                db, session_id, "tool", output, task_id=task_id, tool_call_id=tool_call_id
            )
            
            try:
                from src.services.memory.semantic_memory import semantic_memory
                await semantic_memory.index_event(
                    session_id=session_id,
                    tenant_id=tenant_id or "local",
                    event_type="tool_result",
                    content=f"Tool {tool_name} returned:\n{output}",
                    task_id=task_id
                )
            except Exception as e:
                logger.error(f"[ToolWorker] Failed to index tool result to memory: {e}")
            await db.commit()
            await broker.publish(f"task_log:{task_id}", {
                "event": "tool_done",
                "name": tool_name,
                "result_preview": output[:100]
            })

            logger.info(f"[ToolWorker] Result persisted for {tool_name}.")

        # 5. Re-trigger brain → this closes the ReAct loop, ONLY if no tool is waiting for approval
        if not any_approval_required:
            logger.info(f"[ToolWorker] All batch tools executed. Re-triggering brain.")
            await _re_trigger_brain(broker, task_id, session_id, trace_id, tenant_id)
        else:
            logger.info(f"[ToolWorker] Batch paused for HITL approval.")


async def _re_trigger_brain(broker, task_id: str, session_id: str, trace_id: str = None, tenant_id: str = None):
    """Emit a new AGENT_THINK so the brain re-evaluates with tool results."""
    event = {
        "event_type": "AGENT_THINK",
        "task_id": task_id,
        "session_id": session_id,
        "description": "",  # Empty — context comes from DB now
    }
    if tenant_id:
        event["tenant_id"] = tenant_id
    await broker.publish("task_queue", event, trace_id=trace_id)

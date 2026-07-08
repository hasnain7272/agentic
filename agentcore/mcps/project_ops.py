"""
Project Ops MCP — Project-level diagnostics, compilation verification, and rate limit tracking.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from agentcore.mcps import register_mcp

logger = logging.getLogger(__name__)

@register_mcp
class ProjectOpsMCP:
    name = "project-ops-mcp"
    description = "Workspace diagnostics, API rate limit audits, and code verification"
    TOOLS = {
        "check_rate_limits": {
            "desc": "Check agentcore.log for recent LLM API rate limit or resource exhaustion warnings"
        },
        "verify_code_syntax": {
            "params": {"file_path": "string"},
            "desc": "Execute Python compiler syntax check on a file to verify correctness"
        }
    }

    async def call_tool(self, name: str, args: dict, **kwargs) -> dict:
        if name == "check_rate_limits":
            def read_logs():
                log_path = Path("agentcore.log")
                if not log_path.exists():
                    return {"status": "ok", "message": "No log file found yet."}
                
                # Read last 150 lines
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()[-150:]
                
                content = "".join(lines)
                warnings = []
                import re
                patterns = [
                    r"rate limited",
                    r"ResourceExhausted",
                    r"rate_limited",
                    r"request limit reached",
                    r"circuit breaker"
                ]
                for p in patterns:
                    matches = re.findall(p, content, re.IGNORECASE)
                    if matches:
                        warnings.append(f"Found {len(matches)} occurrences of '{p}'")
                
                return {
                    "status": "warning" if warnings else "ok",
                    "warnings": warnings,
                    "recent_logs_excerpt": content[-4000:]
                }
            
            return await asyncio.to_thread(read_logs)
            
        elif name == "verify_code_syntax":
            file_path = args["file_path"]
            
            def run_compile():
                p = Path(file_path)
                if not p.exists():
                    return {"success": False, "error": f"File '{file_path}' does not exist"}
                if not p.suffix == ".py":
                    # Non-python: check syntax as basic success
                    return {"success": True, "message": f"Non-Python file '{p.name}' exists. Verified basic presence."}
                
                import py_compile
                try:
                    py_compile.compile(str(p), doraise=True)
                    return {"success": True, "message": f"Python syntax check successful for '{p.name}'"}
                except py_compile.PyCompileError as err:
                    return {"success": False, "error": str(err)}
                except Exception as ex:
                    return {"success": False, "error": f"Unexpected compiler error: {ex}"}
            
            return await asyncio.to_thread(run_compile)
            
        raise ValueError(f"Unknown tool: {name}")

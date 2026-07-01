"""
Stdio MCP Spawner - Helper functions for launching MCP subprocesses.
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from src.services.mcp.stdio_messages import MCPProtocolError
from src.services.mcp.stdio_protocol import MCPStdioProtocol

async def spawn_mcp_server(
    command: str,
    args: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Tuple[asyncio.subprocess.Process, MCPStdioProtocol]:
    spawn_env = {}
    if env:
        spawn_env.update(env)
    if "PATH" not in spawn_env:
        import os
        spawn_env["PATH"] = os.environ.get("PATH", "")

    import sys
    if command == "python" or command == "python3":
        command = sys.executable

    process = await asyncio.create_subprocess_exec(
        command,
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=spawn_env if env else None,
        cwd=cwd,
    )

    protocol = MCPStdioProtocol(process)

    return process, protocol

async def initialize_server(
    command: str,
    args: List[str],
    client_info: Dict[str, Any],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Tuple[MCPStdioProtocol, Dict[str, Any]]:
    process, protocol = await spawn_mcp_server(command, args, env, cwd)

    try:
        init_result = await protocol.initialize(client_info)
        return protocol, init_result.get("serverInfo", {})
    except Exception as e:
        await protocol.close()
        raise MCPProtocolError(f"Failed to initialize MCP server: {e}") from e

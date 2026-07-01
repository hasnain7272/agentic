"""
Stdio Writer - Wraps asyncio subprocess streams with robust JSON-RPC
line filtering. Non-JSON lines (logging, warnings) are discarded.
"""
import asyncio
import json
import logging

from src.services.mcp.stdio_messages import MCPProtocolError

logger = logging.getLogger(__name__)

# Maximum time to wait for a response line from the subprocess
READ_TIMEOUT_SECONDS = 120.0


class StdinStdoutWriter:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process

    async def write(self, message: str) -> None:
        if self._process.stdin is None:
            raise MCPProtocolError("Process stdin is None")
        self._process.stdin.write((message + "\n").encode("utf-8"))
        await self._process.stdin.drain()

    async def read_line(self) -> str:
        """Read the next valid JSON-RPC line, skipping non-JSON noise."""
        if self._process.stdout is None:
            raise MCPProtocolError("Process stdout is None")

        while True:
            try:
                line_bytes = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=READ_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                raise MCPProtocolError(
                    f"Timed out waiting for response ({READ_TIMEOUT_SECONDS}s)"
                )

            if not line_bytes:
                raise MCPProtocolError("Process stdout closed unexpectedly")

            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue

            # Only accept lines that look like JSON-RPC objects
            if line.startswith("{"):
                try:
                    json.loads(line)  # validate it's real JSON
                    return line
                except json.JSONDecodeError:
                    logger.debug("[StdioWriter] Skipping malformed JSON: %s", line[:120])
                    continue

            # Skip any non-JSON output (log lines, warnings, etc.)
            logger.debug("[StdioWriter] Skipping non-JSON line: %s", line[:120])

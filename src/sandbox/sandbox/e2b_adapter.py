"""
E2B (Firecracker) Sandbox Adapter

Production-grade isolation using Firecracker MicroVMs via E2B.
Requires E2B_API_KEY.
"""
import os
import logging
from typing import Dict, Any

from src.domain.exceptions import SandboxExecutionError

logger = logging.getLogger(__name__)

class E2BAdapter:
    def __init__(self, template: str = "base"):
        self.template = template
        self.api_key = os.environ.get("E2B_API_KEY")
        if not self.api_key:
            logger.warning("E2B_API_KEY not set. E2B adapter will fail if executed.")

    async def execute(self, command: str, working_dir: str = "/home/user", timeout: int = 30) -> Dict[str, Any]:
        """Execute command in a remote E2B secure sandbox."""
        if not self.api_key:
            raise SandboxExecutionError("E2B Sandbox requested but E2B_API_KEY is missing.")
            
        try:
            from e2b import Sandbox
            
            # Note: e2b python SDK is mostly sync or requires specific async wrappers.
            # Using standard E2B Sandbox for conceptual accuracy.
            sandbox = Sandbox(template=self.template, timeout=timeout)
            
            process = sandbox.process.start(cmd=command, cwd=working_dir)
            process.wait(timeout)
            
            return {
                "exit_code": process.exit_code,
                "stdout": process.stdout[:50000] if process.stdout else "",
                "stderr": process.stderr[:50000] if process.stderr else "",
                "duration_ms": 0.0 # Time abstraction omitted for brevity
            }
            
        except ImportError:
             raise SandboxExecutionError("e2b package not installed.")
        except Exception as e:
            raise SandboxExecutionError(f"E2B execution failed: {str(e)}")

"""
Sandbox Package - Code Execution Environments

Provides secure, isolated code execution with multiple backends:
- DockerSandboxRunner: Production-grade container execution
- LocalSandboxRunner: Development fallback using subprocesses
"""
from src.sandbox.interface import (
    SandboxInterface,
    SandboxLimits,
    SandboxMount,
    ExecutionRequest,
    ExecutionResult,
    SandboxInfo,
    SandboxError,
    SandboxNotFoundError,
    SandboxTimeoutError,
    SandboxResourceError,
    DEFAULT_LIMITS,
    STRICT_LIMITS,
    DEVELOPMENT_LIMITS,
)
from src.sandbox.docker.runner import DockerSandboxRunner
from src.sandbox.local.runner import LocalSandboxRunner, get_local_runner


def get_sandbox_runner(runner_type: str = None):
    """Get sandbox runner by type (docker, local) or from settings."""
    from src.config.settings import get_settings
    
    if runner_type is None:
        settings = get_settings()
        runner_type = settings.sandbox_type
    
    if runner_type == "docker":
        return DockerSandboxRunner()
    elif runner_type == "local":
        return get_local_runner()
    else:
        raise ValueError(f"Unknown sandbox type: {runner_type}")


__all__ = [
    "SandboxInterface",
    "SandboxLimits",
    "SandboxMount",
    "ExecutionRequest",
    "ExecutionResult",
    "SandboxInfo",
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxTimeoutError",
    "SandboxResourceError",
    "DEFAULT_LIMITS",
    "STRICT_LIMITS",
    "DEVELOPMENT_LIMITS",
    "DockerSandboxRunner",
    "LocalSandboxRunner",
    "get_local_runner",
    "get_sandbox_runner",
]
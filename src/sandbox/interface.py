"""
Sandbox Interface - Abstract Base Class for Code Execution

Defines the contract for all sandbox implementations (Docker, Local, K8s).
"""
import abc
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class SandboxLimits:
    """Resource limits for sandbox execution."""
    cpu_limit: str = "1.0"          # CPU cores (e.g., "1.0", "0.5")
    memory_limit: str = "512m"      # Memory (e.g., "512m", "1g")
    timeout_seconds: int = 300      # Max execution time
    pids_limit: int = 100           # Max processes
    disk_limit: str = "1g"          # Disk space
    network_enabled: bool = True    # Network access


@dataclass
class SandboxMount:
    """Volume mount configuration."""
    source: str                     # Host path or volume name
    target: str                     # Container path
    read_only: bool = False


@dataclass
class ExecutionRequest:
    """Request to execute code in sandbox."""
    command: List[str]              # Command and args (e.g., ["python", "script.py"])
    working_dir: str = "/workspace" # Working directory
    environment: Dict[str, str] = None  # Environment variables
    limits: Optional[SandboxLimits] = None
    mounts: List[SandboxMount] = None
    stdin: Optional[str] = None     # Input to stdin
    user: Optional[str] = None      # User to run as


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    oom_killed: bool = False
    error: Optional[str] = None


@dataclass
class SandboxInfo:
    """Sandbox status information."""
    sandbox_id: str
    status: str                     # created, running, stopped, error
    container_id: Optional[str] = None
    created_at: Optional[str] = None
    limits: Optional[SandboxLimits] = None


class SandboxInterface(abc.ABC):
    """Abstract base class for sandbox implementations."""
    
    @abc.abstractmethod
    async def create(self, limits: Optional[SandboxLimits] = None) -> str:
        """
        Create a new sandbox instance.
        
        Returns:
            sandbox_id: Unique identifier for the sandbox
        """
        pass
    
    @abc.abstractmethod
    async def execute(self, sandbox_id: str, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a command in the sandbox.
        
        Args:
            sandbox_id: Sandbox identifier from create()
            request: Execution parameters
            
        Returns:
            ExecutionResult with output and status
        """
        pass
    
    @abc.abstractmethod
    async def upload_file(
        self, 
        sandbox_id: str, 
        local_path: str, 
        remote_path: str
    ) -> bool:
        """
        Upload a file to the sandbox.
        
        Returns:
            True if successful
        """
        pass
    
    @abc.abstractmethod
    async def download_file(
        self, 
        sandbox_id: str, 
        remote_path: str, 
        local_path: str
    ) -> bool:
        """
        Download a file from the sandbox.
        
        Returns:
            True if successful
        """
        pass
    
    @abc.abstractmethod
    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        """
        List files in sandbox directory.
        
        Returns:
            List of file info dicts with name, size, type, modified
        """
        pass
    
    @abc.abstractmethod
    async def delete(self, sandbox_id: str) -> bool:
        """
        Delete/destroy a sandbox.
        
        Returns:
            True if successful
        """
        pass
    
    @abc.abstractmethod
    async def get_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Get sandbox status information."""
        pass
    
    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check sandbox backend health."""
        pass


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class SandboxNotFoundError(SandboxError):
    """Sandbox not found."""
    pass


class SandboxTimeoutError(SandboxError):
    """Execution timed out."""
    pass


class SandboxResourceError(SandboxError):
    """Resource limit exceeded (OOM, CPU, disk)."""
    pass


# Default limits for different scenarios
DEFAULT_LIMITS = SandboxLimits()

STRICT_LIMITS = SandboxLimits(
    cpu_limit="0.5",
    memory_limit="256m",
    timeout_seconds=60,
    pids_limit=50,
    disk_limit="500m",
    network_enabled=False,
)

DEVELOPMENT_LIMITS = SandboxLimits(
    cpu_limit="2.0",
    memory_limit="2g",
    timeout_seconds=600,
    pids_limit=200,
    disk_limit="5g",
    network_enabled=True,
)
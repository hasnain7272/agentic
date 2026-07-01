"""
Docker Resource Limits - Resource Limit Configuration

Defines and validates resource limits for Docker sandbox execution.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from src.config.settings import get_settings


@dataclass
class ResourceLimits:
    """Validated resource limits for container execution."""
    
    # CPU
    cpu_cores: float = 1.0              # CPU cores (0.1 - 8.0)
    cpu_quota: int = 100000             # CFS quota (microseconds)
    cpu_period: int = 100000            # CFS period (microseconds)
    cpu_shares: int = 1024              # CPU shares (relative weight)
    
    # Memory
    memory_bytes: int = 536870912       # Memory limit in bytes (512MB)
    memory_swap_bytes: int = 536870912  # Memory + swap (same = no swap)
    memory_reservation: int = 0         # Soft limit
    kernel_memory: int = 0              # Kernel memory limit
    
    # Processes
    pids_limit: int = 100               # Max processes/threads
    
    # Disk
    disk_quota_bytes: int = 1073741824  # Disk quota (1GB)
    
    # Network
    network_mode: str = "bridge"        # bridge, host, none, container:<id>
    bandwidth_limit: int = 0            # Bytes/sec (0 = unlimited)
    
    # Timeouts
    timeout_seconds: int = 300          # Execution timeout
    startup_timeout: int = 30           # Container startup timeout
    
    # Security
    read_only_rootfs: bool = False      # Read-only root filesystem
    no_new_privileges: bool = True      # Prevent privilege escalation
    capabilities_drop: list = field(default_factory=lambda: ["ALL"])
    capabilities_add: list = field(default_factory=list)
    security_opt: list = field(default_factory=lambda: ["no-new-privileges:true"])
    seccomp_profile: str = "default"    # Seccomp profile
    apparmor_profile: str = ""          # AppArmor profile
    
    # User
    user: str = "sandbox:sandbox"       # User:group to run as
    working_dir: str = "/workspace"     # Working directory
    
    # Tempfs
    tmpfs_mounts: Dict[str, str] = field(default_factory=lambda: {
        : {
        "/tmp": "size=100m,noexec,nosuid,nodev",
        "/run": "size=10m,noexec,nosuid,nodev",
    })
    
    @classmethod
    def from_settings(cls, settings=None) -> "ResourceLimits":
        """Create limits from application settings."""
        settings = settings or get_settings()
        
        return cls(
            cpu_cores=float(settings.sandbox_cpu_limit),
            memory_bytes=cls._parse_memory(settings.sandbox_memory_limit),
            timeout_seconds=settings.sandbox_timeout,
            network_mode=settings.docker_network if settings.sandbox_network_enabled else "none",
            user="sandbox:sandbox",
            working_dir=settings.sandbox_workdir,
        )
    
    @staticmethod
    def _parse_memory(mem_str: str) -> int:
        """Parse memory string to bytes."""
        mem_str = mem_str.lower().strip()
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([kmg]?)b?$', mem_str)
        if not match:
            raise ValueError(f"Invalid memory format: {mem_str}")
        
        value = float(match.group(1))
        unit = match.group(2)
        
        multipliers = {'k': 1024, 'm': 1024**2, 'g': 1024**3, '': 1}
        return int(value * multipliers.get(unit, 1))
    
    def to_docker_create_options(self) -> Dict:
        """Convert to Docker container create options."""
        return {
            "cpu_count": self.cpu_cores,
            "cpu_quota": self.cpu_quota,
            "cpu_period": self.cpu_period,
            "cpu_shares": self.cpu_shares,
            "mem_limit": self.memory_bytes,
            "memswap_limit": self.memory_swap_bytes,
            "mem_reservation": self.memory_reservation or None,
            "kernel_memory": self.kernel_memory or None,
            "pids_limit": self.pids_limit,
            "network_mode": self.network_mode,
            "read_only": self.read_only_rootfs,
            "security_opt": self.security_opt,
            "cap_drop": self.capabilities_drop,
            "cap_add": self.capabilities_add,
            "user": self.user,
            "working_dir": self.working_dir,
            "tmpfs": self.tmpfs_mounts,
        }
    
    def validate(self) -> list:
        """Validate limits and return list of warnings/errors."""
        issues = []
        
        if self.cpu_cores < 0.1 or self.cpu_cores > 8.0:
            issues.append(f"CPU cores should be 0.1-8.0, got {self.cpu_cores}")
        
        if self.memory_bytes < 64 * 1024 * 1024:  # 64MB minimum
            issues.append(f"Memory too low: {self.memory_bytes} bytes (min 64MB)")
        
        if self.memory_bytes > 32 * 1024 * 1024 * 1024:  # 32GB max
            issues.append(f"Memory too high: {self.memory_bytes} bytes (max 32GB)")
        
        if self.pids_limit < 10:
            issues.append(f"PIDs limit too low: {self.pids_limit} (min 10)")
        
        if self.pids_limit > 1000:
            issues.append(f"PIDs limit too high: {self.pids_limit} (max 1000)")
        
        if self.timeout_seconds < 10:
            issues.append(f"Timeout too short: {self.timeout_seconds}s (min 10s)")
        
        if self.timeout_seconds > 3600:
            issues.append(f"Timeout too long: {self.timeout_seconds}s (max 1hr)")
        
        return issues


# Preset limit profiles
PRESET_LIMITS = {
    "minimal": ResourceLimits(
        cpu_cores=0.25,
        memory_bytes=128 * 1024 * 1024,  # 128MB
        pids_limit=20,
        timeout_seconds=30,
        network_mode="none",
    ),
    "strict": ResourceLimits(
        cpu_cores=0.5,
        memory_bytes=256 * 1024 * 1024,  # 256MB
        pids_limit=50,
        timeout_seconds=60,
        network_mode="none",
        read_only_rootfs=True,
    ),
    "default": ResourceLimits(
        cpu_cores=1.0,
        memory_bytes=512 * 1024 * 1024,  # 512MB
        pids_limit=100,
        timeout_seconds=300,
    ),
    "development": ResourceLimits(
        cpu_cores=2.0,
        memory_bytes=2 * 1024 * 1024 * 1024,  # 2GB
        pids_limit=200,
        timeout_seconds=600,
        network_mode="bridge",
    ),
    "heavy": ResourceLimits(
        cpu_cores=4.0,
        memory_bytes=8 * 1024 * 1024 * 1024,  # 8GB
        pids_limit=500,
        timeout_seconds=1800,
        network_mode="bridge",
    ),
}


def get_preset(name: str) -> ResourceLimits:
    """Get a preset limit configuration by name."""
    if name not in PRESET_LIMITS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(PRESET_LIMITS.keys())}")
    return PRESET_LIMITS[name]


def create_limits(
    preset: str = "default",
    **overrides
) -> ResourceLimits:
    """Create limits from preset with optional overrides."""
    limits = get_preset(preset)
    
    for key, value in overrides.items():
        if hasattr(limits, key):
            setattr(limits, key, value)
        else:
            raise ValueError(f"Unknown limit parameter: {key}")
    
    return limits
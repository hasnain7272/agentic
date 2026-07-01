"""
MCP Models and Enums

Core data structures for MCP operations:
- Tool status tracking
- Performance metrics
- Configuration models
"""
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ToolStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class MCPToolMetrics:
    total_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_called: Optional[float] = None

    def record_call(self, latency_ms: float, success: bool) -> None:
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        if not success:
            self.failed_calls += 1
        self.last_called = time.time()

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_called": self.last_called,
        }
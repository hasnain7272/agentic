"""
MCP Rate Limiting and Quota Enforcement

Provides rate limiting for MCP plugin registration and tool execution
with thread-safe in-memory tracking.
"""
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class RateLimitEntry:
    count: int = 0
    first_request: float = field(default_factory=time.time)
    blocked_until: float = 0

    def is_blocked(self) -> bool:
        return time.time() < self.blocked_until

    def increment(self) -> None:
        self.count += 1


class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._entries: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = threading.Lock()

    def check_rate_limit(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        entry = self._entries[key]

        if entry.is_blocked():
            return False, int(entry.blocked_until - now)

        if now - entry.first_request > self.window_seconds:
            entry.count = 0
            entry.first_request = now

        if entry.count >= self.max_requests:
            entry.blocked_until = now + self.window_seconds
            entry.count = 0
            return False, int(self.window_seconds)

        entry.increment()
        return True, 0

    def cleanup_old_entries(self, max_age_seconds: float = 3600) -> None:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._entries.items() if now - v.first_request > max_age_seconds]
            for k in expired:
                del self._entries[k]


_plugin_rate_limiter = RateLimiter(max_requests=50, window_seconds=60.0)
_execution_rate_limiter = RateLimiter(max_requests=200, window_seconds=60.0)


def check_plugin_registration_rate_limit(tenant_id: str) -> Tuple[bool, int]:
    return _plugin_rate_limiter.check_rate_limit(f"plugin_reg:{tenant_id}")


def check_tool_execution_rate_limit(tool_name: str) -> Tuple[bool, int]:
    return _execution_rate_limiter.check_rate_limit(f"tool_exec:{tool_name}")
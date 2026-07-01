"""Message handling logic for context management."""
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.memory.context.checkpoint import CheckpointManager
from src.services.memory.context.models import SessionContext
from src.services.memory.context.windows import WindowManager

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles adding and processing messages in a session context."""

    def __init__(
        self,
        max_recent: int,
        summary_threshold: int,
        windows: WindowManager,
        checkpoint: CheckpointManager
    ):
        self.max_recent = max_recent
        self.summary_threshold = summary_threshold
        self._windows = windows
        self._checkpoint = checkpoint

    async def add_message(
        self,
        context: SessionContext,
        role: str,
        content: str,
        task_id: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_results: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Add message to session context and manage windows."""
        # Create message
        context.last_sequence += 1
        message = {
            "sequence": context.last_sequence,
            "role": role,
            "content": content,
            "task_id": task_id,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add to recent messages
        context.recent_messages.append(message)
        if len(context.recent_messages) > self.max_recent:
            # Move oldest to window
            old_messages = context.recent_messages[:-self.max_recent]
            context.recent_messages = context.recent_messages[-self.max_recent:]

            # Create new window
            if old_messages:
                self._windows.create_window(context, old_messages)
                asyncio.create_task(
                    self._windows.summarize_window(context, context.windows[-1])
                )

        # Update metadata
        context.total_messages += 1
        context.is_dirty = True
        self._checkpoint.mark_dirty(context.session_id)

        # Extract file references
        if "file" in content.lower() or "." in content:
            file_refs = re.findall(r'[\w\-/]+\.\w+', content)
            context.file_references.update(file_refs)

        # Auto-summarize if needed
        if context.total_messages % self.summary_threshold == 0:
            asyncio.create_task(self._windows.summarize_session(context))

        return message

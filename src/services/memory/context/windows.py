"""Window management and summarization logic."""
import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.services.memory.context.models import ContextWindow, SessionContext

logger = logging.getLogger(__name__)


class WindowManager:
    """Manages context windows and their summarization."""

    def __init__(self, window_size: int = 20):
        self.window_size = window_size

    def create_window(
        self,
        context: "SessionContext",
        messages: List[Dict[str, Any]]
    ) -> "ContextWindow":
        """Create a new context window from messages."""
        from src.services.memory.context.models import ContextWindow

        if not messages:
            raise ValueError("Cannot create window from empty messages")

        window = ContextWindow(
            start_sequence=messages[0]["sequence"],
            end_sequence=messages[-1]["sequence"],
            messages=messages,
            token_count=sum(len(m.get("content", "")) for m in messages) // 4
        )

        context.windows.append(window)
        return window

    async def summarize_window(
        self,
        context: "SessionContext",
        window: "ContextWindow"
    ) -> None:
        """Generate summary for a window using LLM."""
        try:
            from src.infrastructure.llm.litellm_client import LLMClient

            llm = LLMClient()

            # Build conversation for summarization
            conversation = "\n".join([
                f"{m['role']}: {m['content'][:200]}"
                for m in window.messages
            ])

            prompt = f"""Summarize this conversation concisely (max 2 sentences):

{conversation}

Summary:"""

            summary = await llm.acomplete(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )

            window.summary = summary
            context.is_dirty = True

        except Exception as e:
            logger.warning(f"[WindowManager] Summarization failed: {e}")

    async def summarize_session(self, context: "SessionContext") -> None:
        """Generate overall session summary."""
        try:
            # Extract key topics
            all_text = " ".join([
                m.get("content", "")
                for w in context.windows[-2:]  # Last 2 windows
                for m in w.messages
            ] + [
                m.get("content", "")
                for m in context.recent_messages
            ])

            # Simple keyword extraction
            words = re.findall(r'\b[A-Z][a-zA-Z]+\b', all_text)
            word_freq: Dict[str, int] = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

            context.key_topics = [
                word for word, count in sorted(
                    word_freq.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                if len(word) > 3
            ]

            context.is_dirty = True

        except Exception as e:
            logger.warning(f"[WindowManager] Session summary failed: {e}")

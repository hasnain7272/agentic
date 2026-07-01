"""Context building for LLM and UI consumption."""
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.services.memory.context.models import SessionContext


class ContextBuilder:
    """Builds context for LLM and UI consumption."""

    def __init__(self, max_recent: int = 10, max_windows: int = 3):
        self.max_recent = max_recent
        self.max_windows = max_windows

    def build_system_prompt(self, context: "SessionContext") -> str:
        """Build system prompt with context metadata."""
        parts = [
            "You are an AI coding assistant. "
            "You have access to the user's codebase and can execute commands."
        ]

        if context.key_topics:
            parts.append(f"Key topics in this session: {', '.join(context.key_topics)}")

        if context.file_references:
            refs = list(context.file_references)[:10]
            parts.append(f"Files discussed: {', '.join(refs)}")

        return "\n\n".join(parts)

    def build_for_llm(
        self,
        context: "SessionContext",
        max_tokens: int = 8000
    ) -> List[Dict[str, str]]:
        """Get context formatted for LLM consumption."""
        messages: List[Dict[str, str]] = []

        # Add system message with summary
        system_content = self.build_system_prompt(context)
        if system_content:
            messages.append({"role": "system", "content": system_content})

        # Add window summaries
        for window in context.windows[-self.max_windows:]:
            if window.summary:
                messages.append({
                    "role": "system",
                    "content": f"[Earlier conversation summary]: {window.summary}"
                })

        # Add recent messages
        for msg in context.recent_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return messages

    def build_for_ui(
        self,
        context: "SessionContext",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get context for UI display."""
        # Combine all messages
        all_messages: List[Dict[str, Any]] = []

        for window in context.windows:
            all_messages.extend(window.messages)

        all_messages.extend(context.recent_messages)

        # Sort by sequence
        all_messages.sort(key=lambda m: m.get("sequence", 0))

        # Return last N
        return all_messages[-limit:]

    def search(
        self,
        context: "SessionContext",
        query: str
    ) -> List[Dict[str, Any]]:
        """Search within session context."""
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        for window in context.windows:
            for msg in window.messages:
                if query_lower in msg.get("content", "").lower():
                    results.append(msg)

        for msg in context.recent_messages:
            if query_lower in msg.get("content", "").lower():
                results.append(msg)

        return results

    def get_file_context(
        self,
        context: "SessionContext",
        filepath: str
    ) -> List[Dict[str, Any]]:
        """Get all messages referencing a specific file."""
        results: List[Dict[str, Any]] = []

        for window in context.windows:
            for msg in window.messages:
                if filepath in msg.get("content", ""):
                    results.append(msg)

        for msg in context.recent_messages:
            if filepath in msg.get("content", ""):
                results.append(msg)

        return results

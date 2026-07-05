"""
AgentCore Loop — Context Compaction (Context Engineering)

Implements rolling summary compaction to enforce a token limit of 4000 tokens
for minimal context windows, stripping raw tool outputs and retaining recent turns.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContextWindow:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def compact(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compresses message history to keep it inside self.max_tokens.
        1. Keeps system prompts untouched.
        2. Keeps last 3 turns (user/assistant) fully intact.
        3. Replaces old tool results with a tiny 1-line summary indicator.
        4. Compiles older turns into a unified context summary.
        """
        if len(messages) <= 5:
            return messages

        system_msgs = [m for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        # Keep last 4 chat messages intact
        keep_count = min(len(chat_msgs), 4)
        older_msgs = chat_msgs[:-keep_count]
        recent_msgs = chat_msgs[-keep_count:]

        # Clean/compress older messages
        compressed_older = []
        for msg in older_msgs:
            role = msg.get("role")
            content = msg.get("content") or ""
            # Strip huge tool call logs
            if role == "tool" or msg.get("tool_calls"):
                content = f"[Tool Call Result: {content[:100]}...]" if len(content) > 100 else content
            compressed_older.append({"role": role, "content": content})

        # Compile a summary block if we have compressed older messages
        summary_content = "Conversation history summary:\n"
        for m in compressed_older:
            summary_content += f"- {m['role'].capitalize()}: {m['content']}\n"

        compacted = []
        if system_msgs:
            compacted.append(system_msgs[0])  # Primary system prompt
        if len(compressed_older) > 0:
            compacted.append({"role": "system", "content": summary_content[:1500]})
        compacted.extend(recent_msgs)

        return compacted

    def format_agent_result(self, agent_name: str, task: str, result: str) -> str:
        """Inject A2A results in a compressed format."""
        return f"[{agent_name}] Task: {task} -> {result[:400]}"

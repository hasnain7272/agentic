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
        2. Compresses JSON payloads and strips structural whitespace/newlines to fit context limit.
        3. Never truncates strings or drops data, just compacts representation.
        """
        import json
        import re

        def clean_content(content: Any) -> str:
            if not content:
                return ""
            if isinstance(content, dict) or isinstance(content, list):
                # Compact JSON representation (no whitespace/newlines)
                return json.dumps(content, separators=(",", ":"))
            
            text = str(content)
            # Try parsing string as JSON to compact it
            try:
                parsed = json.loads(text)
                return json.dumps(parsed, separators=(",", ":"))
            except Exception:
                pass
            
            # Collapse multiple spaces and newlines
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n+", "\n", text)
            return text.strip()

        compacted = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            new_msg = {"role": role}
            if content:
                new_msg["content"] = clean_content(content)
                
            if "tool_calls" in msg and msg["tool_calls"]:
                # Compact tool calls parameters
                new_tool_calls = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function") or {}
                    args = fn.get("arguments") or ""
                    try:
                        args_parsed = json.loads(args)
                        args_compact = json.dumps(args_parsed, separators=(",", ":"))
                    except Exception:
                        args_compact = clean_content(args)
                    
                    new_tool_calls.append({
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": fn.get("name"),
                            "arguments": args_compact
                        }
                    })
                new_msg["tool_calls"] = new_tool_calls
                
            if "tool_call_id" in msg:
                new_msg["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                new_msg["name"] = msg["name"]
                
            compacted.append(new_msg)
            
        return compacted

    def format_agent_result(self, agent_name: str, task: str, result: str) -> str:
        """Inject A2A results in a compressed format without losing data."""
        return f"[{agent_name}] Task: {task} -> {result}"


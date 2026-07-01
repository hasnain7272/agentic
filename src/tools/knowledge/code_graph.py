"""Code knowledge graph for semantic code queries."""
import re
from pathlib import Path
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter
from src.tools.utils.workspace import get_workspace_path
from src.infrastructure.llm.litellm_client import LLMClient


class CodeGraphQueryTool(BaseTool):
    """Query code relationships using natural language."""
    name = "code_graph_query"
    description = "Ask questions about code structure, relationships, and architecture"
    parameters = [
        ToolParameter(name="question", type="string", description="Natural language question about code"),
        ToolParameter(name="context", type="string", description="File or directory to focus on", required=False),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        question = kwargs.get("question")
        context = kwargs.get("context")
        workspace = get_workspace_path(session_id)

        # Gather code context
        code_context = await self._gather_context(workspace, context)

        # Build query prompt
        prompt = f"""Analyze this codebase and answer the question.

Code Context:
{code_context[:4000]}

Question: {question}

Provide:
1. Direct answer
2. Relevant file locations
3. Code examples if applicable
4. Architecture explanation"""

        llm = LLMClient()
        try:
            response = await llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            answer = response.choices[0].message.content

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "context_analyzed": context or "full codebase",
                "files_scanned": len(code_context.split("\n\n")),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _gather_context(self, workspace: Path, context: str = None) -> str:
        """Gather code files for context."""
        if context:
            target = workspace / context
            if target.is_file():
                return target.read_text()
            files = list(target.glob("**/*.py"))[:10]
        else:
            files = list(workspace.glob("**/*.py"))[:20]

        context_parts = []
        for f in files:
            try:
                content = f.read_text()
                # Extract only definitions
                defs = self._extract_definitions(content)
                context_parts.append(f"File: {f.relative_to(workspace)}\n{defs}")
            except Exception:
                continue

        return "\n\n".join(context_parts)

    def _extract_definitions(self, content: str) -> str:
        """Extract class/function definitions from code."""
        lines = content.splitlines()
        definitions = []

        for i, line in enumerate(lines):
            # Match class/def definitions
            if re.match(r'^(class|def)\s+\w+', line):
                definitions.append(line)
                # Get next 2 lines for context
                if i + 1 < len(lines):
                    definitions.append(lines[i + 1])

        return "\n".join(definitions[:50])  # Limit output

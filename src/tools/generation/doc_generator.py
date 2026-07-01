"""Generate documentation for code."""
from pathlib import Path
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter
from src.tools.utils.workspace import get_workspace_path, validate_target_exists
from src.infrastructure.llm.litellm_client import LLMClient


class DocGeneratorTool(BaseTool):
    """Generate API documentation and README updates."""
    name = "generate_docs"
    description = "Generate documentation for code files and APIs"
    parameters = [
        ToolParameter(name="target", type="string", description="File or directory to document"),
        ToolParameter(name="type", type="string", description="Type: api|readme|inline", default="inline"),
        ToolParameter(name="style", type="string", description="Doc style: google|numpy|sphinx", default="google"),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        target = kwargs.get("target")
        doc_type = kwargs.get("type", "inline")
        style = kwargs.get("style", "google")
        workspace = get_workspace_path(session_id)

        is_valid, error = validate_target_exists(workspace, target)
        if not is_valid:
            return {"success": False, "error": error}

        target_path = workspace / target

        if doc_type == "readme":
            return await self._generate_readme(target_path)
        elif doc_type == "api":
            return await self._generate_api_docs(target_path, style)
        else:  # inline
            return await self._add_inline_docs(target_path, style)

    async def _add_inline_docs(self, filepath: Path, style: str) -> Dict:
        """Add docstrings to code."""
        code = filepath.read_text()

        prompt = f"""Add {style}-style docstrings to this Python code.

```python
{code[:1500]}
```

Rules:
- Add docstrings to all functions and classes
- Include Args, Returns, Raises sections
- Keep existing code unchanged
- Return ONLY the updated code

Return the complete file with docstrings added."""

        llm = LLMClient()
        response = await llm.generate(messages=[{"role": "user", "content": prompt}])

        documented_code = response.choices[0].message.content
        documented_code = documented_code.replace("```python", "").replace("```", "").strip()

        return {
            "success": True,
            "type": "inline",
            "style": style,
            "original_file": str(filepath),
            "documented_code": documented_code,
            "changes": documented_code.count('"""') - code.count('"""'),
        }

    async def _generate_readme(self, directory: Path) -> Dict:
        """Generate README for project."""
        # Gather project structure
        files = list(directory.glob("*.py"))[:10]
        structure = "\n".join(f"- {f.name}" for f in files)

        prompt = f"""Generate a README.md for this project.

Project structure:
{structure}

Include:
- Title and description
- Installation instructions
- Usage examples
- Contributing guidelines"""

        llm = LLMClient()
        response = await llm.generate(messages=[{"role": "user", "content": prompt}])

        return {
            "success": True,
            "type": "readme",
            "content": response.choices[0].message.content,
            "suggested_path": str(directory / "README.md"),
        }

    async def _generate_api_docs(self, directory: Path, style: str) -> Dict:
        """Generate API documentation."""
        return {
            "success": True,
            "type": "api",
            "message": "API docs generation - use inline docs first, then pydoc/markdown",
        }

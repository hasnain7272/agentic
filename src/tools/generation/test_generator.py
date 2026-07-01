"""Generate test cases for code."""
from pathlib import Path
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter
from src.tools.utils.workspace import get_workspace_path, get_target_content
from src.infrastructure.llm.litellm_client import LLMClient


class TestGeneratorTool(BaseTool):
    """Generate unit tests for code."""
    name = "generate_tests"
    description = "Generate unit tests for functions and classes"
    parameters = [
        ToolParameter(name="target", type="string", description="File or function to test"),
        ToolParameter(name="framework", type="string", description="pytest|unittest", default="pytest"),
        ToolParameter(name="coverage", type="string", description="basic|comprehensive|edge_cases", default="comprehensive"),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        target = kwargs.get("target")
        framework = kwargs.get("framework", "pytest")
        coverage = kwargs.get("coverage", "comprehensive")
        workspace = get_workspace_path(session_id)

        # Read target file
        result = get_target_content(workspace, target)
        if not result["success"]:
            return result

        code = result["content"]
        target_path = result["path"]

        # Build generation prompt
        prompt = f"""Generate {coverage} {framework} tests for this code.

File: {target}

```python
{code[:2000]}
```

Generate tests that cover:
{"- Happy path" if coverage in ["basic", "comprehensive", "edge_cases"] else ""}
{"- Edge cases (empty inputs, None, large values)" if coverage in ["comprehensive", "edge_cases"] else ""}
{"- Error conditions (exceptions, invalid inputs)" if coverage in ["comprehensive", "edge_cases"] else ""}
{"- Boundary conditions and stress cases" if coverage == "edge_cases" else ""}

Return ONLY the test file content, no explanations."""

        llm = LLMClient()
        try:
            response = await llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            test_code = response.choices[0].message.content
            # Clean markdown fences
            test_code = test_code.replace("```python", "").replace("```", "").strip()

            # Determine test file path
            test_filename = f"test_{target_path.stem}.py"
            test_path = workspace / "tests" / test_filename

            return {
                "success": True,
                "target": target,
                "framework": framework,
                "test_code": test_code,
                "test_file": str(test_path.relative_to(workspace)),
                "suggestion": f"Save to tests/{test_filename}",
            }
        except Exception as e:
            return {"success": False, "error": f"Generation failed: {str(e)}"}

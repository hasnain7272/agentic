"""AI-powered code review tool."""
from pathlib import Path
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.llm.litellm_client import LLMClient
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class CodeReviewTool(BaseTool):
    """Generate code reviews using AI analysis."""
    name = "code_review"
    description = "Review code changes for quality, patterns, and improvements"
    parameters = [
        ToolParameter(name="filepath", type="string", description="File to review"),
        ToolParameter(name="focus", type="string", description="Focus: style|performance|security|architecture|all", default="all"),
        ToolParameter(name="pr_diff", type="string", description="PR diff content (optional)", required=False),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        filepath = kwargs.get("filepath")
        focus = kwargs.get("focus", "all")
        pr_diff = kwargs.get("pr_diff")
        workspace = Path(f"/workspace/{session_id}/repos")

        # Get file content or diff
        if pr_diff:
            content = pr_diff
            context = "PR changes"
        else:
            file_path = workspace / filepath
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {filepath}"}
            content = file_path.read_text()
            context = filepath

        # Build review prompt
        prompts = {
            "style": "Review code style, naming conventions, and readability.",
            "performance": "Review for performance optimizations and efficiency.",
            "security": "Review for security vulnerabilities and best practices.",
            "architecture": "Review code structure, design patterns, and maintainability.",
            "all": "Review for style, performance, security, and architecture.",
        }

        review_prompt = f"""{prompts.get(focus, prompts["all"])}

File: {context}

```
{content[:3000]}
```

Provide:
1. Overall score (1-10)
2. 3 specific issues with line numbers
3. Positive findings
4. Actionable recommendations

Format as JSON with keys: score, issues, positives, recommendations"""

        # Get AI review
        llm = LLMClient()
        try:
            response = await llm.generate(
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.3
            )

            review_text = response.choices[0].message.content

            # Parse review
            review = self._parse_review(review_text)

            return {
                "success": True,
                "filepath": filepath,
                "focus": focus,
                "review": review,
                "raw_response": review_text[:500],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Review failed: {str(e)}",
            }

    def _parse_review(self, text: str) -> Dict:
        """Parse AI review response."""
        # Simple extraction
        lines = text.splitlines()

        review = {
            "score": 7,
            "issues": [],
            "positives": [],
            "recommendations": [],
        }

        current_section = None
        for line in lines:
            if "score" in line.lower() and any(c.isdigit() for c in line):
                digits = ''.join(c for c in line if c.isdigit())
                if digits:
                    review["score"] = min(int(digits), 10)
            elif "issue" in line.lower() or "problem" in line.lower():
                current_section = "issues"
            elif "positive" in line.lower() or "good" in line.lower():
                current_section = "positives"
            elif "recommendation" in line.lower():
                current_section = "recommendations"
            elif line.strip().startswith(("-", "*", "1.", "2.", "3.")):
                if current_section:
                    review[current_section].append(line.strip(" -*1234567890."))

        return review

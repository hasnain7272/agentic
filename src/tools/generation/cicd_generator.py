"""Generate CI/CD pipeline configurations."""
from pathlib import Path
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter


class CICDGeneratorTool(BaseTool):
    """Generate CI/CD pipelines for projects."""
    name = "generate_cicd"
    description = "Generate GitHub Actions, GitLab CI, or Azure Pipelines"
    parameters = [
        ToolParameter(name="platform", type="string", description="github_actions|gitlab_ci|azure", default="github_actions"),
        ToolParameter(name="language", type="string", description="Project language", required=False),
        ToolParameter(name="tests", type="boolean", description="Include test stage", default=True),
        ToolParameter(name="deploy", type="boolean", description="Include deploy stage", default=False),
    ]
    requires_sandbox = False

    TEMPLATES = {
        "github_actions": {
            "python": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest
      - run: ruff check .
      {deploy_step}""",
            "node": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm test
      - run: npm run lint
      {deploy_step}""",
        },
    }

    DEPLOY_STEP_GH = """  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to production
        run: echo "Add deployment command here"
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}"""

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        platform = kwargs.get("platform", "github_actions")
        language = kwargs.get("language") or await self._detect_language(session_id)
        tests = kwargs.get("tests", True)
        deploy = kwargs.get("deploy", False)

        template = self.TEMPLATES.get(platform, {}).get(language)
        if not template:
            template = self._generate_generic(platform, language, tests, deploy)

        # Add deploy step if requested
        deploy_step = self.DEPLOY_STEP_GH if deploy else ""
        config = template.format(deploy_step=deploy_step)

        # Determine file path
        if platform == "github_actions":
            filepath = ".github/workflows/ci.yml"
        elif platform == "gitlab_ci":
            filepath = ".gitlab-ci.yml"
        else:
            filepath = "azure-pipelines.yml"

        return {
            "success": True,
            "platform": platform,
            "language": language,
            "config": config,
            "filepath": filepath,
            "stages": ["checkout", "install", "test"] + (["deploy"] if deploy else []),
        }

    async def _detect_language(self, session_id: str) -> str:
        """Auto-detect project language."""
        workspace = Path(f"/workspace/{session_id}/repos")
        if (workspace / "requirements.txt").exists():
            return "python"
        if (workspace / "package.json").exists():
            return "node"
        if (workspace / "pom.xml").exists():
            return "java"
        return "python"  # default

    def _generate_generic(self, platform: str, language: str, tests: bool, deploy: bool) -> str:
        """Generate generic pipeline."""
        return f"""# {platform} pipeline for {language}
# TODO: Customize for your project
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: echo "Add {language} build commands"
      {"- name: Test\n        run: echo 'Add test commands'" if tests else "# No tests configured"}
      {"- name: Deploy\n        run: echo 'Add deploy commands'" if deploy else "# No deploy configured"}"""

"""Dependency management with safety checks."""
from pathlib import Path
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class DependencyManagerTool(BaseTool):
    """Manage dependencies with conflict resolution."""
    name = "manage_dependencies"
    description = "Update dependencies with testing and rollback"
    parameters = [
        ToolParameter(name="package", type="string", description="Package name or 'all'"),
        ToolParameter(name="strategy", type="string", description="patch|minor|major", default="minor"),
        ToolParameter(name="test", type="boolean", description="Run tests after update", default=True),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        package = kwargs.get("package", "all")
        strategy = kwargs.get("strategy", "minor")
        run_tests = kwargs.get("test", True)
        workspace = f"/workspace/{session_id}/repos"

        executor = await get_sandbox_executor()
        changes = []

        # Detect package manager
        if await self._has_file(workspace, "requirements.txt"):
            manager = "pip"
            changes = await self._update_pip(executor, workspace, package, strategy)
        elif await self._has_file(workspace, "package.json"):
            manager = "npm"
            changes = await self._update_npm(executor, workspace, package, strategy)
        else:
            return {"success": False, "error": "No requirements.txt or package.json found"}

        # Test if requested
        test_results = None
        if run_tests and changes:
            test_results = await self._run_tests(executor, workspace, manager)

        # Rollback if tests failed
        if test_results and not test_results.get("passed"):
            await self._rollback(executor, workspace, manager)
            return {
                "success": False,
                "changes": changes,
                "test_results": test_results,
                "rolled_back": True,
                "error": "Tests failed, changes rolled back",
            }

        # Commit if successful
        if changes:
            await executor.execute(
                command=f"cd {workspace} && git add . && git commit -m 'Update dependencies: {package}'"
            )

        return {
            "success": True,
            "manager": manager,
            "package": package,
            "strategy": strategy,
            "changes": changes,
            "test_results": test_results,
            "committed": len(changes) > 0,
        }

    async def _has_file(self, workspace: str, filename: str) -> bool:
        """Check if file exists in workspace."""
        return (Path(workspace) / filename).exists()

    async def _update_pip(self, executor, workspace: str, package: str, strategy: str) -> List[Dict]:
        """Update pip packages."""
        if package == "all":
            cmd = f"cd {workspace} && pip install -r requirements.txt --upgrade --upgrade-strategy {strategy} 2>&1"
        else:
            cmd = f"cd {workspace} && pip install {package} --upgrade 2>&1"

        result = await executor.execute(command=cmd)
        return [{"package": package, "updated": result.exit_code == 0}]

    async def _update_npm(self, executor, workspace: str, package: str, strategy: str) -> List[Dict]:
        """Update npm packages."""
        if package == "all":
            cmd = f"cd {workspace} && npm update 2>&1"
        else:
            cmd = f"cd {workspace} && npm install {package}@latest 2>&1"

        result = await executor.execute(command=cmd)
        return [{"package": package, "updated": result.exit_code == 0}]

    async def _run_tests(self, executor, workspace: str, manager: str) -> Dict:
        """Run test suite."""
        if manager == "pip":
            cmd = f"cd {workspace} && python -m pytest --tb=short -q 2>&1"
        else:
            cmd = f"cd {workspace} && npm test 2>&1"

        result = await executor.execute(command=cmd)
        return {
            "passed": result.exit_code == 0,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
        }

    async def _rollback(self, executor, workspace: str, manager: str):
        """Rollback changes."""
        await executor.execute(command=f"cd {workspace} && git checkout -- .")

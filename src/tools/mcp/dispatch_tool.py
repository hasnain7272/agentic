"""
Dispatch Output Tool — Agentic decision for product delivery.
"""
import logging
from typing import Dict, Any, List
from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import execute_sandboxed

logger = logging.getLogger(__name__)

class DispatchOutputTool(BaseTool):
    """Dispatch agent output to specific destinations."""
    name = "dispatch_output"
    description = (
        "Finalize the task by dispatching modified files to their destination. "
        "Use this after you have finished all processing and verification."
    )
    parameters = [
        ToolParameter(name="files", type="array", description="List of file paths to dispatch"),
        ToolParameter(
            name="destination", 
            type="string", 
            description="Target destination: 'sandbox' (for UI download), 'git' (commit to repo), 'workspace' (persistent folder)"
        ),
        ToolParameter(
            name="destination_params", 
            type="object", 
            description="Optional parameters: { repo_url: '', branch: '', folder: '' }",
            required=False
        ),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        files = kwargs.get("files", [])
        destination = kwargs.get("destination", "sandbox")
        params = kwargs.get("destination_params", {})
        
        # In this pragmatic implementation, the agent uses bash_execute 
        # to physically move files within the isolated mount.
        
        if destination == "sandbox":
            # Files in /workspace/ are already in the 'sandbox' UI
            return {"success": True, "message": f"Files {files} are ready for download in your sandbox."}
            
        if destination == "workspace":
            target_dir = params.get("folder", "persistent")
            cmd = f"mkdir -p /workspace/{target_dir} && cp {' '.join(files)} /workspace/{target_dir}/"
            res = await execute_sandboxed(command=cmd)
            return {"success": res.exit_code == 0, "message": f"Files synced to workspace folder: {target_dir}"}

        if destination == "git":
            # The agent should use the specialized git tools for this.
            # This is a hint to the agent to use git_commit next.
            return {
                "success": True, 
                "message": "Dispatch to Git initiated. Please use 'git_commit' and 'git_create_pr' to finalize the sync."
            }

        return {"success": False, "error": f"Unsupported destination: {destination}"}

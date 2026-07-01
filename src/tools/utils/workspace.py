"""Workspace utilities for tools."""
from pathlib import Path
from typing import Dict, Optional, Tuple


def get_workspace_path(session_id: str, subpath: str = "repos") -> Path:
    """Get standardized workspace path for session."""
    return Path(f"/workspace/{session_id}/{subpath}")


def validate_target_exists(workspace: Path, target: str) -> Tuple[bool, Optional[str]]:
    """Validate target exists in workspace.

    Returns (is_valid, error_message)
    """
    target_path = workspace / target
    if not target_path.exists():
        return False, f"Target not found: {target}"
    return True, None


def get_target_content(workspace: Path, target: str, limit: int = 2000) -> Dict:
    """Read target file content with error handling.

    Returns dict with success, content, error keys.
    """
    target_path = workspace / target
    if not target_path.exists():
        return {"success": False, "error": f"File not found: {target}"}

    try:
        content = target_path.read_text()
        return {
            "success": True,
            "content": content,
            "truncated": len(content) > limit,
            "path": target_path,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to read {target}: {str(e)}"}


def sanitize_shell_content(content: str) -> str:
    """Escape content for safe shell usage."""
    return content.replace("'", "'\"'\"'")

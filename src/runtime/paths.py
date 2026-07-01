"""
Runtime Paths - Workspace Path Resolution

Provides secure path resolution within the workspace root.
"""
import os
from pathlib import Path
from typing import Union

from src.config.settings import get_settings

# Default workspace root
DEFAULT_WORKSPACE_ROOT = "/workspace"


def get_workspace_root() -> Path:
    """Get the workspace root directory."""
    settings = get_settings()
    root = getattr(settings, 'workspace_root', DEFAULT_WORKSPACE_ROOT)
    return Path(root).resolve()


def resolve_workspace_path(path: Union[str, Path]) -> Path:
    """
    Resolve a path relative to workspace root.
    
    Prevents path traversal attacks by ensuring the resolved
    path stays within the workspace root.
    """
    workspace_root = get_workspace_root()
    target_path = Path(path)
    
    # If absolute, make it relative to workspace root
    if target_path.is_absolute():
        try:
            target_path = target_path.relative_to(workspace_root)
        except ValueError:
            # Path is outside workspace root, anchor it
            target_path = workspace_root / target_path.name
    
    # Resolve relative to workspace root
    resolved = (workspace_root / target_path).resolve()
    
    # Security check: ensure path is within workspace
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        raise ValueError(f"Path traversal attempt blocked: {path}")
    
    return resolved


def is_within_workspace(path: Union[str, Path]) -> bool:
    """Check if a path is within the workspace root."""
    try:
        resolved = resolve_workspace_path(path)
        return True
    except ValueError:
        return False


def get_relative_path(path: Union[str, Path]) -> Path:
    """Get path relative to workspace root."""
    workspace_root = get_workspace_root()
    resolved = resolve_workspace_path(path)
    return resolved.relative_to(workspace_root)


def ensure_workspace_dir(path: Union[str, Path]) -> Path:
    """Ensure a directory exists within workspace."""
    resolved = resolve_workspace_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


# For backwards compatibility
WORKSPACE_ROOT = get_workspace_root()
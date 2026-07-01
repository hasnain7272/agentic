"""Router registration for FastAPI."""
from fastapi import FastAPI

from src.api.rest.routers import (
    chat, sessions, tasks, folders as folders_router,
    git_mount, github_auth
)
import src.api.rest.routers.auth as auth_module


def include_routers(app: FastAPI):
    """Register all API routers."""
    app.include_router(tasks.router)
    app.include_router(sessions.router)
    app.include_router(folders_router.router)
    app.include_router(chat.router)
    app.include_router(git_mount.router)
    app.include_router(github_auth.router)
    app.include_router(auth_module.router)
    import src.api.rest.routers.state_stream as state_stream_module
    app.include_router(state_stream_module.router)
    import src.api.rest.routers.workspace as workspace_module
    app.include_router(workspace_module.router)
    import src.api.rest.routers.mcp_plugins as mcp_plugins_module
    app.include_router(mcp_plugins_module.router)
    import src.api.rest.routers.mcp_plugins_info as mcp_plugins_info_module
    app.include_router(mcp_plugins_info_module.router)
    import src.api.rest.routers.mcp_stdio as mcp_stdio_module
    app.include_router(mcp_stdio_module.router)
    import src.api.rest.routers.mcp_stdio_info as mcp_stdio_info_module
    app.include_router(mcp_stdio_info_module.router)
    import src.api.rest.routers.settings as settings_module
    app.include_router(settings_module.router)

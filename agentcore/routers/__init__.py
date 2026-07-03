from .health import health_router
from .auth import auth_router
from .sessions import sessions_router
from .chat import chat_router
from .tasks import tasks_router
from .tools import tools_router
from .governance import governance_router
from .approvals import approvals_router
from .settings import settings_router
from .mcp import mcp_router

all_routers = [
    health_router,
    auth_router,
    sessions_router,
    chat_router,
    tasks_router,
    tools_router,
    governance_router,
    approvals_router,
    settings_router,
    mcp_router,
]

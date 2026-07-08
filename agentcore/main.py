"""
AgentCore — Entry Point

Usage:
    python -m agentcore.main              # default: localhost:8000
    python -m agentcore.main --port 9000  # custom port
    python -m agentcore.main --reload     # hot-reload for development
"""
import argparse
import asyncio
import logging
import sys

import uvicorn

from agentcore.config import get_settings


def setup_logging(level: str = "INFO"):
    """Configure structured logging."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)
    
    try:
        file_handler = logging.FileHandler("agentcore.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:
        pass


async def startup():
    """Run startup tasks: DB init, tool registration, etc."""
    from agentcore.database import init_db
    from agentcore.tools import get_tool_registry

    # Initialize database tables
    await init_db()

    # Initialize tool registry (auto-discovers all built-in tools)
    registry = get_tool_registry()
    registry.get_all_names()  # trigger lazy discovery

    logging.getLogger(__name__).info(f"Startup complete — {len(registry.get_all_names())} tools registered")


def main():
    settings = get_settings()

    parser = argparse.ArgumentParser(description="AgentCore Runtime")
    parser.add_argument("--host", default=settings.api_host)
    parser.add_argument("--port", type=int, default=settings.api_port)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default=settings.log_level)
    args = parser.parse_args()

    setup_logging(args.log_level)

    # Run async startup
    asyncio.run(startup())

    print("=" * 60)
    print("  AGENTCORE RUNTIME")
    print("=" * 60)
    print(f"  API:  http://{args.host}:{args.port}")
    print(f"  Docs: http://{args.host}:{args.port}/api/docs")
    print(f"  Env:  {settings.app_env}")
    print("=" * 60)

    import signal
    import os

    def force_exit_handler(sig, frame):
        print("\n[AgentCore] Force terminating process...")
        os._exit(0)

    signal.signal(signal.SIGINT, force_exit_handler)
    signal.signal(signal.SIGTERM, force_exit_handler)

    uvicorn.run(
        "agentcore.api:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()

"""
Project Kernel Runtime — Entry Point

Usage:
python main.py # default: localhost:8089
python main.py --port 9000 # custom port
python main.py --reload # hot-reload for development
"""
import argparse
import asyncio
import uvicorn
import os
import sys


def run_startup():
    """Run startup tasks before server starts."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

    try:
        from scripts.startup import main as startup_main
        asyncio.run(startup_main())
    except Exception as e:
        print(f"Warning: Startup tasks failed: {e}")
        print("Continuing anyway...")


def main():
    # Run startup first
    run_startup()

    parser = argparse.ArgumentParser(description="Project Kernel Runtime")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-worker", action="store_true", help="Disable background worker")
    args = parser.parse_args()

    os.environ["HYBRID_MODE"] = "false" if args.no_worker else "true"

    mode_name = "HYBRID MODE (API + WORKER)" if not args.no_worker else "STATELESS MODE"

    print("=" * 60)
    print(f"PROJECT KERNEL RUNTIME: {mode_name}")
    print("=" * 60)
    if not args.no_worker:
        print("Worker running in background. Use --no-worker for API-only.")
    print(f"Access: http://{args.host}:{args.port}")
    print("=" * 60)

    print(f"\n[OK] Server ready at: http://{args.host}:{args.port}")
    print(f"[OK] API docs at: http://{args.host}:{args.port}/api/docs")
    print("=" * 60)

    uvicorn.run(
        "src.api.fastapi_gateway:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

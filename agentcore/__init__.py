"""
AgentCore - Minimalist Agentic Runtime

A consolidated, ~3,500-line agentic platform with:
- config.py    — Pydantic settings
- auth.py      — JWT + middleware + RBAC
- database.py  — SQLAlchemy models + session
- governance.py — Roles, policies, approval workflows
- sandbox.py   — Docker & local sandbox execution
- mcp.py       — MCP client, protocol, stdio
- tools.py     — Tool registry, schemas, builtin tools
- agent_loop.py — ReAct orchestration engine
- api.py       — FastAPI REST endpoints
- websocket.py — WebSocket handlers
- web_search.py — Multi-provider web search
- main.py      — Entry point
"""

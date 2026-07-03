"""
AgentCore - Minimalist Agentic Runtime

A database-only agentic platform with:
- config.py    — Pydantic settings
- auth.py      — JWT + middleware
- database.py  — SQLAlchemy models + session
- governance.py — Policies, approval workflows
- mcp.py       — MCP client, protocol, stdio
- tools.py     — Tool registry, schemas, skilled tools
- agent_loop.py — ReAct orchestration engine
- api.py       — FastAPI REST endpoints
- websocket.py — WebSocket handlers
- main.py      — Entry point
"""

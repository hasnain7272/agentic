# Project Kernel Runtime

Project Kernel Runtime is an embeddable agent backend for coding workflows. It is built around one real execution path instead of multiple competing runtimes.

## What It Does

- Runs an agentic loop over a workspace
- Uses a model-agnostic LLM adapter
- Executes built-in file, shell, git, and web tools
- Persists sessions, tasks, and audit logs in SQLite
- Supports human approval for risky actions
- Exposes FastAPI endpoints for chat, workspace, governance, telemetry, MCP, and settings

## Core Architecture

```text
project_kernel_runtime/
├── kernel/
│   ├── orchestrator.py
│   ├── runtime.py
│   ├── tool_executor.py
│   ├── universal_tools.py
│   ├── governance.py
│   ├── session_manager.py
│   └── task_state_machine.py
├── cognition/
│   └── llm_provider.py
├── services/
│   ├── fastapi_server.py
│   └── api/
├── data/
├── runtime.yaml
├── pyproject.toml
└── main.py
```

## Install

```bash
pip install -r requirements.txt
# or
pip install -e .
```

## Run

**Standard Mode:**
```bash
python main.py --host 0.0.0.0 --port 8089
```

**Cloudflare Tunnel Mode (for GitHub Pages Frontend):**
```powershell
.\start_with_tunnel.ps1
```

## Key Endpoints

- `GET /health`
- `GET /status/full`
- `POST /api/chat/execute`
- `GET /api/chat/tasks`
- `GET /api/sessions`
- `GET /api/settings`
- `GET /api/settings/health`
- `GET /api/governance/audit`
- `GET /api/governance/approvals`
- `GET /api/workspace/tree`
- `POST /api/workspace/file`
- `POST /api/workspace/patch`
- `GET /api/telemetry/stream`
- `GET /api/mcp/servers`

## Verification

```bash
.venv\Scripts\python.exe verify_runtime_smoke.py
.venv\Scripts\python.exe test_real_integration.py
```

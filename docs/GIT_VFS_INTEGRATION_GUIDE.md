# Git Virtual File System - Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │  FileExplorer   │  │   DiffViewer    │  │ MountDialog  │  │
│  │   Component     │  │   Component     │  │  Component   │  │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘  │
│           │                   │                   │          │
│           └───────────────────┼───────────────────┘          │
│                               │                              │
│                    ┌──────────┴──────────┐                  │
│                    │    useWebSocket       │                  │
│                    │    (Real-time sync)   │                  │
│                    └──────────┬──────────┘                  │
└───────────────────────────────┼─────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                         BACKEND (FastAPI)                        │
│  ┌────────────────────────────┼──────────────────────────┐     │
│  │                    API Gateway                          │     │
│  └────────────────────────────┼──────────────────────────┘     │
│                               │                                  │
│  ┌────────────────────────────┼──────────────────────────┐     │
│  │                    git_mount.py Router                 │     │
│  │  - POST /mount           │                              │     │
│  │  - GET /mount/{id}/tree  │                              │     │
│  │  - POST /mount/{id}/read │                              │     │
│  │  - POST /mount/{id}/write│                              │     │
│  └────────────────────────────┼──────────────────────────┘     │
│                               │                                  │
│  ┌────────────────────────────┼──────────────────────────┐     │
│  │              GitVirtualFileSystem (GVFS)               │     │
│  │                   (git_virtual_fs.py)                  │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │     │
│  │  │   Clone     │  │   Virtual   │  │    Change     │  │     │
│  │  │  Repository │  │   Overlay   │  │    Tracking   │  │     │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │     │
│  └────────────────────────────┼──────────────────────────┘     │
│                               │                                  │
│  ┌────────────────────────────┼──────────────────────────┐     │
│  │              ContextPersistenceManager                 │     │
│  │                  (context_manager.py)                  │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │     │
│  │  │   Sliding   │  │   Smart     │  │  Background   │  │     │
│  │  │  Windows    │  │ Summarizer  │  │  Checkpoint   │  │     │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │     │
│  └───────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Git Virtual File System (GVFS)

**What it does:**
- Mounts any Git repository to a session
- Creates a virtual filesystem overlay
- Tracks changes separately from working tree
- Enables multiple sessions on same repo

**Security:**
- Repositories cloned to ephemeral storage
- Changes stored in session-isolated directories
- Auth tokens encrypted at rest
- No changes written to original repo without explicit commit

**Performance:**
- Lazy-loading: Files only loaded when accessed
- Incremental persistence: Only deltas saved
- LRU cache for active sessions
- Background checkpointing

### 2. Session Context Persistence

**What it does:**
- Efficiently persists conversation context
- Sliding window approach for long sessions
- Automatic summarization of old messages
- Semantic search capability

**Benefits:**
- Sessions survive server restarts
- Scales to thousands of messages
- LLM context always optimized
- Background processing doesn't block UI

### 3. Real-time Sync

**Features:**
- WebSocket for file change notifications
- Automatic reconnection
- Message queueing during offline
- Connection state management

## Usage Example

### Mounting a Repository

```typescript
// In your React component
const [isMountDialogOpen, setIsMountDialogOpen] = useState(false);
const [mountInfo, setMountInfo] = useState<{repo_url: string, branch: string} | null>(null);

const handleMount = async (repoUrl: string, branch: string) => {
  const response = await fetch('/api/v1/git/mount', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: currentSessionId,
      repo_url: repoUrl,
      branch: branch,
      auth_token: gitToken, // Optional
    }),
  });
  
  const data = await response.json();
  setMountInfo({ repo_url: data.repo_url, branch: data.branch });
};
```

### File Explorer

```tsx
<FileExplorer
  sessionId={currentSessionId}
  onFileSelect={(file) => setSelectedFile(file)}
  onFileOpen={(file) => openFileEditor(file)}
/>
```

### Reading/Writing Files

```typescript
// Read file
const readFile = async (path: string) => {
  const response = await fetch(`/api/v1/git/mount/${sessionId}/read`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  
  const data = await response.json();
  return data.content;
};

// Write file
const writeFile = async (path: string, content: string) => {
  const response = await fetch(`/api/v1/git/mount/${sessionId}/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  });
  
  // File changes automatically synced via WebSocket
};
```

### Viewing Diff

```tsx
<DiffViewer
  oldContent={originalContent}
  newContent={modifiedContent}
  oldLabel="HEAD"
  newLabel="Modified"
  fileName="src/main.py"
/>
```

## Database Schema

```sql
-- Sessions now support Git mounting
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS git_repo_url VARCHAR;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS git_branch VARCHAR DEFAULT 'main';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS git_commit_sha VARCHAR;

-- Messages already exist - context manager optimizes storage
-- No schema changes needed for messages
```

## API Endpoints

### Git Mount Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/git/mount` | Mount repository to session |
| GET | `/api/v1/git/mount/{session_id}/tree` | Get file tree |
| POST | `/api/v1/git/mount/{session_id}/read` | Read file |
| POST | `/api/v1/git/mount/{session_id}/write` | Write file |
| POST | `/api/v1/git/mount/{session_id}/delete` | Delete file |
| GET | `/api/v1/git/mount/{session_id}/changes` | Get all changes |
| POST | `/api/v1/git/mount/{session_id}/diff` | Get file diff |
| POST | `/api/v1/git/mount/{session_id}/commit` | Commit changes |
| POST | `/api/v1/git/mount/{session_id}/unmount` | Unmount repository |
| WS | `/api/v1/git/mount/{session_id}/files/stream` | Real-time file changes |

### Context Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/git/mount/{session_id}/context` | Get session context |
| POST | `/api/v1/git/mount/{session_id}/context/search` | Search context |

## Environment Variables

```bash
# Git Virtual FS Storage
GVFS_STORAGE_PATH=/var/lib/gvfs  # Where clones and changes stored
GVFS_MAX_CLONE_SIZE=100MB        # Max repo size to clone

# Context Manager
CONTEXT_WINDOW_SIZE=20           # Messages per window
CONTEXT_MAX_RECENT=10            # Keep last N in memory
CONTEXT_SUMMARY_THRESHOLD=100    # Summarize after N messages
CONTEXT_CACHE_SIZE=1000          # Max sessions in LRU cache

# WebSocket
WS_RECONNECT_INTERVAL=3000       # Reconnect interval (ms)
WS_MAX_RECONNECT_ATTEMPTS=5      # Max reconnect attempts
```

## Installation

```bash
# Install additional dependencies
pip install cachetools aiofiles

# Frontend dependencies
npm install @types/diff
```

## Testing

```bash
# Run GVFS tests
pytest tests/test_git_virtual_fs.py -v

# Run context manager tests
pytest tests/test_context_manager.py -v
```

## Production Considerations

1. **Storage**: Ensure `/var/lib/gvfs` has sufficient space
2. **Cleanup**: Implement cleanup job for abandoned mounts
3. **Monitoring**: Track storage usage per session
4. **Security**: Rotate auth tokens, audit access
5. **Backup**: Session state is ephemeral - persist important commits

## Future Enhancements

- [ ] Multi-branch support
- [ ] Git LFS support
- [ ] Submodule support
- [ ] Blame/annotations
- [ ] Branch management UI
- [ ] Pull request creation
- [ ] Code review workflow
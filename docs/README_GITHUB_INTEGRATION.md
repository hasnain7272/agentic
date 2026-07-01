# GitHub Integration Setup

## Environment Variables

Add these to your `.env` file:

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your_github_app_client_id
GITHUB_CLIENT_SECRET=your_github_app_client_secret

# Optional: GitHub Enterprise
# GITHUB_API_URL=https://github.enterprise.com/api/v3
```

## Setup Steps

1. **Create GitHub App**
   - Go to GitHub → Settings → Developer Settings → GitHub Apps
   - Click "New GitHub App"
   - Set callback URL: `http://localhost:5173/github/callback`
   - Enable permissions:
     - `contents: read`
     - `metadata: read`
   - Generate private key (not needed for OAuth flow)

2. **Get Credentials**
   - Copy **Client ID**
   - Generate **Client Secret** and copy it

3. **Add to Environment**
   ```bash
   export GITHUB_CLIENT_ID="Iv23lixxx"
   export GITHUB_CLIENT_SECRET="xxxxxxxx"
   ```

## API Endpoints

### OAuth Flow

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/github/auth` | GET | Start OAuth flow (redirects to GitHub) |
| `/api/v1/github/connect` | POST | Complete OAuth (callback) |
| `/api/v1/github/repos` | GET | List user's repositories |
| `/api/v1/github/disconnect` | DELETE | Remove GitHub connection |

### Git Virtual File System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/git/mount` | POST | Mount a repository |
| `/api/v1/git/mount/{id}/tree` | GET | Get file tree |
| `/api/v1/git/mount/{id}/read` | POST | Read file |
| `/api/v1/git/mount/{id}/write` | POST | Write file |
| `/api/v1/git/mount/{id}/delete` | POST | Delete file |
| `/api/v1/git/mount/{id}/changes` | GET | Get changes |
| `/api/v1/git/mount/{id}/diff` | POST | Get diff |
| `/api/v1/git/mount/{id}/commit` | POST | Commit changes |
| `/api/v1/git/mount/{id}/unmount` | POST | Unmount repository |

## Frontend Integration

The UI now includes:
- **GitHub Connect Button** in the header
- **File Explorer** sidebar with Git status indicators
- **Repo Picker** modal for selecting repositories
- **Diff Viewer** for viewing changes

## Testing

1. Start the server: `python -m uvicorn src.api.fastapi_gateway:app --reload`
2. Open the UI: `http://localhost:5173`
3. Click "Connect GitHub" button
4. Authorize the app
5. Select a repository
6. Browse files with real-time Git status

## Production Considerations

- Store `GITHUB_CLIENT_SECRET` in Kubernetes secrets
- Use HTTPS callback URLs
- Enable state parameter validation
- Rate limit OAuth endpoints
- Encrypt tokens at rest (already implemented)
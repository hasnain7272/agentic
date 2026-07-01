# Project Kernel Runtime - Deployment Guide

## Quick Start (5 minutes)

### Option 1: Local Development (Recommended for testing)

```powershell
# 1. Clone and enter directory
cd project_kernel_runtime

# 2. Run the deployment script
.\scripts\deploy-local.ps1

# 3. Open browser
# http://localhost:8089
```

### Option 2: Docker Compose (Recommended for production-like setup)

```bash
# 1. Copy environment template
copy .env.example .env

# 2. Start services
docker-compose up -d

# 3. View logs
docker-compose logs -f app
```

### Option 3: Manual Setup

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment
$env:ENVIRONMENT="development"
$env:ALLOW_ANON_LOCAL="true"

# 4. Run startup
python scripts\startup.py

# 5. Start server
python main.py
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/kernel.db` | Database connection |
| `REDIS_URL` | (empty) | Redis connection (optional) |
| `JWT_SECRET` | (generated) | JWT signing key |
| `APP_SECRET_KEY` | (generated) | Encryption key |
| `HYBRID_MODE` | `true` | Run worker in same process |
| `ALLOW_ANON_LOCAL` | `true` | Allow anonymous access |

### Production Settings

```bash
# Production environment
ENVIRONMENT=production
ALLOW_ANON_LOCAL=false
HYBRID_MODE=false

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kernel

# Redis (required for production)
REDIS_URL=redis://localhost:6379/0

# CORS (restrict to your domain)
CORS_ORIGINS=https://app.yourdomain.com
```

## Production Deployment Options

### 1. Render.com (Recommended for MVP)

**Cost**: $0 (free tier) - $7/month (paid)

```yaml
# render.yaml
services:
  - type: web
    name: kernel-runtime
    runtime: python
    plan: free
    buildCommand: pip install -r requirements-prod.txt
    startCommand: python main.py
    envVars:
      - key: DATABASE_URL
        value: sqlite:///data/kernel.db
      - key: JWT_SECRET
        generateValue: true
      - key: APP_SECRET_KEY
        generateValue: true
    disk:
      name: data
      mountPath: /data
      sizeGB: 1
```

Deploy: `render deploy`

### 2. Railway.app

**Cost**: $5/month minimum

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### 3. Fly.io

**Cost**: $0 (free tier) - $1.94/month (after free tier)

```bash
# Install Fly CLI
winget install Fly.io.flyctl

# Launch
flyctl launch

# Deploy
flyctl deploy
```

### 4. DigitalOcean App Platform

**Cost**: $12/month minimum

```yaml
# .do/app.yaml
name: kernel-runtime
services:
  - name: api
    source_dir: /
    github:
      repo: yourusername/kernel-runtime
      branch: main
    run_command: python main.py
    env_vars:
      - key: DATABASE_URL
        scope: RUN_TIME
      - key: JWT_SECRET
        scope: RUN_TIME
```

### 5. Self-Hosted (VPS)

**Cost**: $5-20/month (DigitalOcean, Linode, Hetzner)

```bash
# 1. SSH to server
ssh root@your-server

# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Clone and deploy
git clone https://github.com/yourusername/kernel-runtime.git
cd kernel-runtime

# 4. Configure
cp .env.example .env
nano .env  # Edit configuration

# 5. Start
docker-compose up -d

# 6. Setup reverse proxy (Caddy)
docker run -d -p 80:80 -p 443:443 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v caddy_data:/data \
  caddy:2 caddy reverse-proxy --from yourdomain.com --to app:8089
```

## Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new feature"

# Run migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Monitoring

### Health Checks

- `GET /health` - Basic health
- `GET /api/v1/health/workers` - Worker status
- `GET /api/v1/metrics` - Prometheus metrics

### Logs

```bash
# Local
python main.py 2>&1 | tee runtime.log

# Docker
docker-compose logs -f app

# View specific service
journalctl -u kernel-runtime -f
```

## Troubleshooting

### Database Errors

```bash
# Reset database
rm data/kernel.db
python scripts/startup.py
```

### Port Already in Use

```bash
# Change port
python main.py --port 8089
```

### Redis Connection Failed

```bash
# Run without Redis
$env:REDIS_URL=""
python main.py
```

## Security Checklist

- [ ] Change default JWT_SECRET
- [ ] Change default APP_SECRET_KEY
- [ ] Set strong passwords
- [ ] Enable HTTPS in production
- [ ] Restrict CORS origins
- [ ] Set rate limits
- [ ] Enable audit logging
- [ ] Configure backup strategy

## Support

- Documentation: https://docs.kernel-runtime.dev
- Issues: https://github.com/yourusername/kernel-runtime/issues
- Discord: https://discord.gg/kernel-runtime

---

**Ready to deploy?** Start with Option 1 (local) to test, then use Option 2 or a cloud provider for production.

# 🚀 Production Deployment Checklist

## Pre-Deployment

### Environment Setup
- [ ] Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`
- [ ] Set `DATABASE_URL` for PostgreSQL
- [ ] Set `REDIS_URL` for Redis
- [ ] Set `ENCRYPTION_KEY` for secrets
- [ ] Set `KUBERNETES_MODE=true` for production
- [ ] Set `ALLOW_ANON_LOCAL=false` for production

### Database
- [ ] Run migrations: `alembic upgrade head`
- [ ] Verify database connectivity
- [ ] Check indices are created

### Build
- [ ] Build Docker image: `docker build -f Dockerfile.prod -t antigravity/runtime:3.0.0 .`
- [ ] Push to registry: `docker push antigravity/runtime:3.0.0`
- [ ] Tag as latest: `docker tag antigravity/runtime:3.0.0 antigravity/runtime:latest`

## Deployment

### Kubernetes
```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply secrets (manual)
kubectl apply -f k8s/secret.yaml

# 3. Apply config maps
kubectl apply -f k8s/configmap.yaml

# 4. Deploy infrastructure
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 5. Wait for infrastructure
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s

# 6. Deploy application
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/brain-worker.yaml
kubectl apply -f k8s/tool-worker.yaml

# 7. Apply networking
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/network-policies.yaml

# 8. Verify deployment
kubectl get pods -n antigravity
kubectl get svc -n antigravity
kubectl get ingress -n antigravity
```

### Verification
- [ ] Health check passes: `curl https://api.antigravity.ai/health`
- [ ] API docs accessible: `https://api.antigravity.ai/api/docs`
- [ ] GitHub OAuth working
- [ ] File Explorer loads
- [ ] WebSocket connections working

## Post-Deployment

### Monitoring
- [ ] Check Prometheus metrics
- [ ] Verify Grafana dashboards
- [ ] Set up alerts
- [ ] Check logs: `kubectl logs -l app=antigravity-api`

### Scaling
- [ ] Verify HPA is working
- [ ] Test autoscaling under load
- [ ] Check resource limits

### Security
- [ ] Verify network policies
- [ ] Check RBAC permissions
- [ ] Test path traversal protection
- [ ] Verify rate limiting

## Rollback Plan

```bash
# Rollback to previous version
kubectl rollout undo deployment/antigravity-api
kubectl rollout undo deployment/antigravity-brain-worker
kubectl rollout undo deployment/antigravity-tool-worker

# Or specific revision
kubectl rollout undo deployment/antigravity-api --to-revision=2
```

## Troubleshooting

### Common Issues

**Database connection failed:**
```bash
kubectl logs -l app=postgres
kubectl exec -it deployment/antigravity-api -- python -c "from src.infrastructure.db.session import engine; print('DB OK')"
```

**Redis connection failed:**
```bash
kubectl logs -l app=redis
kubectl exec -it deployment/antigravity-api -- python -c "import redis; r = redis.from_url('redis://redis:6379'); print(r.ping())"
```

**App won't start:**
```bash
kubectl describe pod -l app=antigravity-api
kubectl logs -l app=antigravity-api --tail=100
```

## Success Criteria

- [ ] All pods running: `kubectl get pods -n antigravity`
- [ ] Services accessible
- [ ] Health checks passing
- [ ] GitHub OAuth working
- [ ] File operations working
- [ ] No errors in logs
- [ ] Response time < 200ms
- [ ] 99.9% uptime

## Contact

- On-call: ops@antigravity.ai
- Slack: #production-alerts
- PagerDuty: Antigravity Production
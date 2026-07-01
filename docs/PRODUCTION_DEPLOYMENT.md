# Production Deployment Guide

This guide covers deploying the Antigravity Runtime in a production environment with all the production-grade fixes implemented.

## What's Been Fixed

### ✅ 1. Redis Streams (Message Durability)
**Problem:** Fire-and-forget Pub/Sub lost messages when consumers crashed  
**Solution:** Redis Streams with Consumer Groups + Dead Letter Queues

**Key Features:**
- Guaranteed message delivery via ACKs
- Consumer groups for horizontal scaling
- Message claiming from dead consumers
- Dead letter queue after 3 retries
- Auto-retry with exponential backoff

**Migration:**
```python
# OLD (fire-and-forget)
await broker.publish("task_queue", {...})

# NEW (durable streams)
await broker.publish("task_queue", {...}, trace_id=trace_id)

# Consumer
await broker.subscribe("task_queue", "brain-workers", callback)
```

### ✅ 2. Distributed Tracing (OpenTelemetry)
**Problem:** No way to trace requests through the system  
**Solution:** OpenTelemetry with automatic instrumentation

**Key Features:**
- Automatic FastAPI instrumentation
- SQLAlchemy query tracing
- Redis operation tracing
- Custom spans for tool execution
- Export to Jaeger/Tempo

**Environment Variables:**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=antigravity-api
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=1.0
```

### ✅ 3. Kubernetes Sandbox (Security)
**Problem:** Direct `docker run` subprocess calls are insecure  
**Solution:** Kubernetes Jobs with proper security contexts

**Key Features:**
- Runs as non-root user (UID 1000)
- Read-only root filesystem
- Resource limits (CPU/Memory)
- Security contexts (drop all capabilities)
- Network isolation
- Automatic cleanup (TTL)

**K8s Requirements:**
```yaml
# Labels for sandbox nodes
kubectl label nodes <node-name> sandbox-enabled=true

# Taint sandbox nodes
kubectl taint nodes <node-name> sandbox=true:NoSchedule
```

### ✅ 4. Parallel Tool Execution
**Problem:** Tools executed sequentially (slow)  
**Solution:** Dependency-aware parallel execution

**Key Features:**
- Analyzes tool dependencies automatically
- Groups independent tools into parallel batches
- Respects file write/read dependencies
- Configurable max parallelism (default: 5)

**Usage:**
```python
# Tools are automatically parallelized
results = await router.execute_parallel(
    tool_calls=[tool1, tool2, tool3],
    session_id=session_id,
    registry=registry
)
```

### ✅ 5. Circuit Breakers & Rate Limiting
**Problem:** No protection against cascade failures  
**Solution:** Circuit breakers + distributed rate limiting

**Key Features:**
- Circuit breakers for LLM API, Sandbox, Database
- Automatic recovery testing (HALF_OPEN state)
- Distributed rate limiting with Redis
- Sliding window algorithm

**Usage:**
```python
from src.infrastructure.resilience.circuit_breaker import with_llm_circuit_breaker

@with_llm_circuit_breaker
async def call_llm_api(...):
    return await litellm.acompletion(...)
```

---

## Deployment Steps

### Step 1: Install Dependencies

```bash
pip install -e ".[dev]"
```

### Step 2: Start Infrastructure

```bash
# Start all production services
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale brain-worker=4 --scale tool-worker=6
```

### Step 3: Setup Kubernetes Sandbox (Required for Production)

```bash
# Create sandbox namespace and resources
kubectl apply -f k8s/sandbox-namespace.yaml

# Verify
kubectl get all -n antigravity-sandbox
```

### Step 4: Configure Environment

Create `.env` file:

```bash
# Database
POSTGRES_USER=antigravity
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=kernel

# Redis
REDIS_URL=redis://redis:6379/0

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Kubernetes
KUBECONFIG=/path/to/kubeconfig
K8S_NAMESPACE=antigravity-sandbox

# Worker scaling
BRAIN_WORKER_REPLICAS=4
TOOL_WORKER_REPLICAS=6
```

### Step 5: Verify Deployment

```bash
# Health check
curl http://localhost:8089/health

# Check metrics
curl http://localhost:8089/metrics

# View traces in Jaeger
open http://localhost:16686

# View dashboards in Grafana
open http://localhost:3000
```

---

## Architecture Changes

### New File Structure

```
src/
├── infrastructure/
│   ├── queue/
│   │   └── redis_streams_broker.py    # ✅ NEW: Durable streams
│   ├── observability/
│   │   └── tracing.py                  # ✅ NEW: OpenTelemetry
│   ├── sandbox/
│   │   └── kubernetes_executor.py      # ✅ NEW: K8s jobs
│   └── resilience/
│       ├── circuit_breaker.py          # ✅ NEW: Circuit breakers
│       └── rate_limiter.py             # ✅ NEW: Rate limiting
└── services/
    └── tool_execution/
        └── parallel_router.py          # ✅ NEW: Parallel execution
```

### Worker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Redis Streams                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ task_queue   │  │execution_queue│  │  DLQ          │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                      │
    ┌─────┴─────┐          ┌─────┴─────┐
    │  Brain    │          │   Tool    │
    │  Workers  │          │  Workers  │
    │  (x4)     │          │  (x6)     │
    └───────────┘          └───────────┘
```

---

## Monitoring

### Key Metrics

| Metric | Endpoint | Description |
|--------|----------|-------------|
| Circuit Breaker Status | `/health/circuits` | Shows open/closed circuits |
| Rate Limit Status | `/health/ratelimits` | Shows rate limit usage |
| Message Stream Info | `/health/streams` | Shows stream lengths and lag |

### Alerts

Configure alerts for:

1. **Circuit Breaker Open**
   ```
   When: circuit_breaker_open > 0
   Severity: Warning
   ```

2. **Dead Letter Queue Growth**
   ```
   When: dlq_size > 100
   Severity: Critical
   ```

3. **Worker Lag**
   ```
   When: consumer_lag > 1000
   Severity: Warning
   ```

4. **Message Processing Time**
   ```
   When: message_duration_p95 > 30s
   Severity: Warning
   ```

---

## Troubleshooting

### Issue: Messages not being processed

```bash
# Check consumer groups
redis-cli XINFO GROUPS task_queue
redis-cli XINFO GROUPS execution_queue

# Check pending messages
redis-cli XPENDING task_queue brain-workers

# Claim stuck messages manually
redis-cli XCLAIM task_queue brain-workers <consumer> 60000 <message-id>
```

### Issue: Circuit breaker constantly opening

```bash
# Check circuit breaker metrics
curl http://localhost:8089/health/circuits

# Check logs
kubectl logs -f deployment/api -n default | grep "CircuitBreaker"
```

### Issue: Sandbox jobs failing

```bash
# Check job status
kubectl get jobs -n antigravity-sandbox

# Check pod logs
kubectl logs -n antigravity-sandbox job/<job-name>

# Check resource quotas
kubectl describe resourcequota sandbox-quota -n antigravity-sandbox
```

---

## Performance Tuning

### Redis Streams

```python
# Increase batch size for higher throughput
await broker.subscribe(
    stream="task_queue",
    group="brain-workers",
    callback=process,
    batch_size=50,  # default: 10
    block_ms=5000
)
```

### Parallel Tool Execution

```bash
# Increase max parallelism
export MAX_PARALLEL_TOOLS=10
```

### Circuit Breaker

```python
# Adjust thresholds
from src.infrastructure.resilience.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=10,  # More lenient
    timeout=120.0,         # Longer timeout
    success_threshold=5
)
```

---

## Security Checklist

- [ ] Kubernetes namespace created with restricted PSP
- [ ] ServiceAccount with minimal permissions
- [ ] NetworkPolicy denying egress by default
- [ ] ResourceQuotas configured
- [ ] LimitRange for default resource limits
- [ ] Secrets stored in Kubernetes secrets (not env vars)
- [ ] API keys encrypted at rest
- [ ] RBAC configured
- [ ] Pod security policies enforced

---

## Migration from v2.x

### Breaking Changes

1. **Queue System**: Old Pub/Sub code won't work with new Streams
2. **Sandbox**: Docker subprocess replaced with K8s jobs
3. **Tracing**: Now required (add OTEL env vars)

### Migration Steps

1. Backup database
2. Deploy new infrastructure (Redis, PostgreSQL, K8s)
3. Deploy new workers
4. Switch traffic
5. Monitor for issues

---

## Support

For production support:
1. Check logs: `kubectl logs deployment/api`
2. Check traces: http://localhost:16686
3. Check metrics: http://localhost:9090
4. Check dashboards: http://localhost:3000
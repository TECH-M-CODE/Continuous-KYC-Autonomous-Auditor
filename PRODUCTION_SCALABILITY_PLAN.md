# CXKYC — Demo to Production-Scalable Migration Plan

Status: **proposal / not yet implemented**. This document is a step-by-step plan only —
no source files have been changed. Each phase lists exactly which existing files
need to change and shows the code delta.

## 1. Where we are today (as-built, verified against the repo)

| Concern | Current implementation | Why it blocks scaling |
|---|---|---|
| Database | SQLite, sync `SQLAlchemy` engine, WAL mode (`app/models/base.py`) | Single file, single writer. Can't be shared by >1 backend container. |
| Cache | `LocalMemoryCache` — an in-process dict with TTL (`app/infrastructure/cache.py`), used by `LLMGateway` and `SanctionsListAdapter` | Dies on restart, not shared across replicas → every replica re-calls the LLM / re-fetches sanctions lists. `redis_url` already exists in `app/config.py` but nothing actually connects to Redis yet. |
| Real-time events (SSE) | `AsyncioBroker` — an in-process `asyncio.Queue` fan-out (`app/infrastructure/broker.py`), consumed by `app/api/sse.py` | Events published on replica A never reach a browser tab connected to replica B. Horizontal scaling silently breaks the live alert feed. |
| Background jobs | `AsyncIOScheduler` (APScheduler, in-process) for ingestion adapters + a bare `asyncio.create_task` for the agent pipeline ("Loop B") in `app/main.py` lifespan | If you run 3 backend replicas, you get 3x ingestion polls and 3x LLM agent runs on the same events — duplicate SARs, duplicate Gemini spend, race conditions on the same DB rows. |
| Vector store | `chromadb.PersistentClient` writing to local disk (`knowledge/store.py`, `data/chroma`) | File-based, single-node. Breaks the moment more than one container needs it, and isn't captured by a container volume strategy today. |
| Auth | `app/api/deps.py` returns a hardcoded `SYSTEM_USER_ID`; `jwt_secret_key` exists in config but is never used to verify anything | No real authentication/authorization exists at all yet. |
| Rate limiting | `rate_limit_per_minute` exists in config, nothing enforces it | No protection against abusive clients. |
| Reverse proxy | `frontend/nginx.conf` proxies `/api` straight to a single `backend:8000` upstream | No load balancing, no health-check-based failover. |
| Orchestration | `docker-compose.yml` — one `backend` container, one `frontend` container, bind-mounted `./data` | No scaling, no resource limits, no restarts on failed health checks beyond `unless-stopped`. |
| Schema migrations | None — SQLAlchemy models with no Alembic | Schema changes require manual DB surgery or a full drop/recreate. |
| Observability | `otel_exporter_otlp_endpoint` exists in config, unused. `X-Trace-Id` header is generated per request but not correlated to logs/metrics. | Can't see what's happening across replicas in production. |

The good news: the codebase already has the right **seams**. `LocalMemoryCache` and
`AsyncioBroker` are used behind narrow interfaces (`get/set/invalidate`,
`subscribe/publish/unsubscribe`), so they can be swapped for Redis-backed
implementations without touching call sites in `LLMGateway`, `sse.py`, or the agents.
That is the main lever this plan pulls.

## 2. Target architecture

```mermaid
flowchart TB
    subgraph Edge
        LB[Load Balancer / Nginx or Traefik<br/>TLS termination, health checks]
    end

    subgraph Web tier - stateless, N replicas
        FE1[frontend static - nginx]
        API1[backend replica 1 - FastAPI/uvicorn]
        API2[backend replica 2 - FastAPI/uvicorn]
        API3[backend replica N]
    end

    subgraph Worker tier - singleton via leader lock
        SCHED[ingestion scheduler worker]
        AGENTS[agent pipeline worker - Loop B]
    end

    subgraph Data tier
        PG[(PostgreSQL - primary + read replica)]
        REDIS[(Redis - cache, pub/sub, locks, rate limit)]
        VEC[(pgvector in Postgres OR Chroma server)]
        S3[(Object storage - SAR PDFs, datasets)]
    end

    subgraph Observability
        OTEL[OTel Collector]
        PROM[Prometheus]
        GRAF[Grafana]
        LOKI[Loki / log aggregation]
    end

    LB --> FE1
    LB --> API1
    LB --> API2
    LB --> API3

    API1 & API2 & API3 --> PG
    API1 & API2 & API3 --> REDIS
    API1 & API2 & API3 --> VEC
    API1 & API2 & API3 -. SSE via Redis pub/sub .- REDIS

    SCHED --> PG
    SCHED --> REDIS
    AGENTS --> PG
    AGENTS --> REDIS
    AGENTS --> VEC
    AGENTS -. publishes alert/SAR events .-> REDIS

    API1 & API2 & API3 & SCHED & AGENTS -.-> OTEL --> PROM & LOKI --> GRAF
```

Key architectural decisions:

1. **Web tier becomes fully stateless.** No in-process cache, no in-process broker,
   no in-process schedulers. Any replica can serve any request.
2. **Background work moves out of the web process** into one or two dedicated
   worker services, protected by a Redis leader lock so only one instance runs
   ingestion/agent jobs at a time — even if the worker deployment itself is scaled
   for HA (standby takes over via lock expiry, not by running duplicate work).
3. **Redis becomes the shared nervous system**: LLM/sanctions cache, SSE pub/sub,
   distributed lock for the scheduler, and the rate-limiter's counters.
4. **Postgres replaces SQLite** as the system of record; **pgvector** is
   recommended over standing up a separate Chroma server, so you have one
   database to back up, scale, and reason about transactionally (see §5 for the
   alternative if you want to keep Chroma).

## 3. Phased migration

Do these in order — each phase is independently deployable and testable, and
later phases assume earlier ones are done. Rough effort estimates assume one
engineer familiar with the codebase.

---

### Phase 0 — Guardrails (0.5 day)

- Add a `docker-compose.override.yml`-based local dev flow so `docker-compose up`
  still works exactly as today while you build the prod path in parallel
  (`docker-compose.prod.yml`).
- Pin dependency versions in `requirements.txt` (several are `>=` today, e.g.
  `SQLAlchemy>=2.0.0`, `fastapi>=0.100.0`) — for production you want reproducible
  builds. Use `pip-compile` or switch to `uv`/`poetry` lockfiles.
- Add a `/api/v1/health/ready` vs `/api/v1/health/live` split if not already
  present (check `app/api/health.py`) — the load balancer and orchestrator need
  these to differ: liveness = "process is up", readiness = "DB + Redis reachable".

---

### Phase 1 — PostgreSQL migration (1.5–2 days)

**Why first:** everything else (multi-replica web tier, workers) is unsafe until
the datastore itself supports concurrent writers.

**1.1 — Add async Postgres driver + Alembic**

`requirements.txt` additions:
```diff
 SQLAlchemy>=2.0.0
 aiosqlite
+asyncpg
+psycopg2-binary   # sync driver, used by Alembic's offline/online migration runner
+alembic>=1.13
```

**1.2 — Rewrite `app/models/base.py` to async engine**

Current file uses a sync `create_engine` + SQLite-specific `PRAGMA` listener. Replace with:

```python
# app/models/base.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(
    settings.database_url,       # postgresql+asyncpg://user:pass@postgres:5432/cxkyc
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # survives Postgres restarts / LB failover without stale connections
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

This touches every repository in `app/repositories/*.py` and `app/repositories/unit_of_work.py`
— they need `async def` methods and `await session.execute(...)` instead of sync
calls. This is the single biggest mechanical change in the whole migration;
budget the most review time here. Search for every `Session` usage:

```
grep -rn "SessionLocal\|Session(" app/repositories app/services
```

**1.3 — `app/config.py` — default URL becomes Postgres**

```diff
-    database_url: str = "sqlite+aiosqlite:///./data/sentinelai.db"
+    database_url: str = "postgresql+asyncpg://cxkyc:cxkyc@localhost:5432/cxkyc"
```
Keep SQLite as a fallback for unit tests via `.env.test` — don't force
integration-test infra onto every unit test file in `tests/`.

**1.4 — Alembic setup**

```
alembic init app/migrations
```
Point `env.py` at `Base.metadata` and `settings.database_url`. Generate the
initial migration from the existing models (`app/models/*.py`):
```
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
From here on, every model change ships with a migration — no more implicit
`create_all()`.

**1.5 — `docker-compose.yml` — add Postgres service**

```diff
 services:
+  postgres:
+    image: postgres:16-alpine
+    container_name: cxkyc_postgres
+    environment:
+      - POSTGRES_USER=cxkyc
+      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?required}
+      - POSTGRES_DB=cxkyc
+    volumes:
+      - pgdata:/var/lib/postgresql/data
+    healthcheck:
+      test: ["CMD-SHELL", "pg_isready -U cxkyc"]
+      interval: 5s
+      timeout: 3s
+      retries: 5
+    restart: unless-stopped
+
   backend:
     build:
       context: .
       dockerfile: Dockerfile
     container_name: sentinelai_backend
+    depends_on:
+      postgres:
+        condition: service_healthy
     environment:
-      - DATABASE_URL=sqlite:///./data/sentinelai.db
+      - DATABASE_URL=postgresql+asyncpg://cxkyc:${POSTGRES_PASSWORD:?required}@postgres:5432/cxkyc
       - ENVIRONMENT=development
     restart: unless-stopped
+
+volumes:
+  pgdata:
```

Data migration: write a one-off script that reads every row out of
`data/sentinelai.db` via `sqlite3`/SQLAlchemy and bulk-inserts into Postgres,
or — since this is pre-production — just re-run the ingestion adapters against
a fresh Postgres DB and treat the SQLite file as disposable demo data.

---

### Phase 2 — Redis: real cache + distributed pub/sub (1–1.5 days)

**2.1 — Redis-backed cache, same interface as `LocalMemoryCache`**

Add `app/infrastructure/redis_cache.py` implementing the exact same public
surface (`get`, `set`, `delete`, `invalidate`, `stats`, `__contains__`) so
`LLMGateway` (`app/infrastructure/llm_gateway.py:139`) and
`SanctionsListAdapter` (`app/services/ingestion/sanctions_list.py:99`) don't
change their call sites — only what gets injected changes.

```python
# app/infrastructure/redis_cache.py
import json
import redis.asyncio as redis
from app.infrastructure.cache import CacheStats, DEFAULT_TTL_SECONDS

class RedisCache:
    def __init__(self, client: redis.Redis, *, namespace: str = "cxkyc") -> None:
        self._r = client
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get(self, key: str, default=None):
        raw = await self._r.get(self._k(key))
        return json.loads(raw) if raw is not None else default

    async def set(self, key: str, value, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        await self._r.set(self._k(key), json.dumps(value), ex=ttl_seconds)

    async def delete(self, key: str) -> bool:
        return bool(await self._r.delete(self._k(key)))

    async def invalidate(self, prefix: str) -> int:
        keys = [k async for k in self._r.scan_iter(match=f"{self._ns}:{prefix}*")]
        return await self._r.delete(*keys) if keys else 0
```

Note `LLMGateway.complete()` and `_try_once` are already `async def`, so
awaiting the cache is a one-line change per call site
(`self._cache.set(...)` → `await self._cache.set(...)`). `LocalMemoryCache`
stays in the codebase as-is for unit tests that don't want a live Redis.

**2.2 — `app/config.py`** — `redis_url` already exists (line 27); add a factory:

```python
# app/infrastructure/redis_client.py
from functools import lru_cache
import redis.asyncio as redis
from app.config import settings

@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=False, max_connections=50)
```

**2.3 — Redis-backed broker, replacing `AsyncioBroker` for cross-replica SSE**

This is the change that actually makes horizontal scaling of the web tier
possible. `app/infrastructure/broker.py` currently fans out only within one
process's memory. Add a Redis Pub/Sub-backed implementation with the same
`subscribe`/`publish`/`unsubscribe`/`subscription()` contract documented in the
existing broker's docstring:

```python
# app/infrastructure/redis_broker.py
import asyncio, json
import redis.asyncio as redis
from app.infrastructure.broker import Message, TOPICS, UnknownTopicError

CHANNEL = "cxkyc:events"

class RedisBroker:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def publish(self, topic: str, payload) -> None:
        if topic not in TOPICS:
            raise UnknownTopicError(topic)
        # fire-and-forget, matches AsyncioBroker's "publish never blocks" contract
        asyncio.create_task(self._r.publish(CHANNEL, json.dumps({"topic": topic, "payload": payload}, default=str)))

    async def subscription(self):
        pubsub = self._r.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async def gen():
                async for msg in pubsub.listen():
                    if msg["type"] != "message":
                        continue
                    data = json.loads(msg["data"])
                    yield Message(topic=data["topic"], payload=data["payload"])
            yield gen()
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.close()
```

`app/api/sse.py:40` (`with broker.subscription() as queue:`) becomes
`async with broker.subscription() as gen: async for message in gen:` — a small,
contained change in one file. Every agent/service that calls
`broker.publish(...)` (search `from app.infrastructure.broker import broker`)
needs no change beyond the import, since the call signature is preserved.

Single Redis channel (rather than one channel per topic) keeps ordering
semantics identical to today's `subscribe_all()` behavior, which the SSE
handler relies on.

**2.4 — Rate limiting on Redis**

`rate_limit_per_minute` already exists in `app/config.py:21` unused. Add
`slowapi` (Redis-backed limiter) as FastAPI middleware in `app/main.py`:

```diff
+from slowapi import Limiter
+from slowapi.util import get_remote_address
+
+limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url,
+                   default_limits=[f"{settings.rate_limit_per_minute}/minute"])
+app.state.limiter = limiter
+app.add_middleware(SlowAPIMiddleware)
```

**2.5 — `docker-compose.yml` — add Redis**

```diff
+  redis:
+    image: redis:7-alpine
+    container_name: cxkyc_redis
+    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD:?required}"]
+    volumes:
+      - redisdata:/data
+    healthcheck:
+      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
+      interval: 5s
+      timeout: 3s
+      retries: 5
+    restart: unless-stopped
```
and add `redisdata:` to the `volumes:` block, and `redis: {condition: service_healthy}` to `backend`'s `depends_on`.

---

### Phase 3 — Extract background workers (1.5 days)

**Problem:** `app/main.py`'s `lifespan()` starts `AsyncIOScheduler` (ingestion
adapters, via `build_scheduler` in `app/services/ingestion/base.py:266`) and a
bare `asyncio.create_task(poll_unprocessed_events(handler=run_pipeline))` for
the agent pipeline (Loop B), both *inside the same process that serves HTTP
traffic*. Scale the web tier to 3 replicas today and you get 3 schedulers and 3
Loop B pollers racing over the same rows.

**3.1 — Split entrypoints**

- `app/main.py` (web): keep only the FastAPI app + routers. Remove the
  scheduler/Loop B startup from `lifespan()`.
- New `app/worker.py`: a standalone process that starts `build_scheduler(...)`
  and `poll_unprocessed_events(handler=run_pipeline)` — everything currently in
  `lifespan()` after the router registration.

**3.2 — Leader lock so exactly one worker replica is active**

Even the worker deployment should be able to run 2 replicas for HA without
double-processing. Use a Redis lock with TTL + renewal (`redis.asyncio.lock.Lock`
with a background renewal task, or the `python-redis-lock`/`redlock-py`
pattern):

```python
# app/worker.py (sketch)
import asyncio
from app.infrastructure.redis_client import get_redis

LOCK_KEY = "cxkyc:worker:leader"

async def run_as_leader(coro_factory):
    r = get_redis()
    while True:
        lock = r.lock(LOCK_KEY, timeout=30, blocking_timeout=5)
        if await lock.acquire():
            try:
                await coro_factory()  # runs scheduler + Loop B until cancelled/crashes
            finally:
                await lock.release()
        else:
            await asyncio.sleep(10)  # standby, retry acquiring
```

**3.3 — New Dockerfile target + compose service**

Reuse the existing `Dockerfile` (same dependencies) with a different `CMD`:
```diff
-CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
+CMD ["python", "-m", "app.worker"]
```
via a build stage or a second Dockerfile (`Dockerfile.worker`) that `COPY`s the
same code and just overrides `CMD`. In `docker-compose.yml`:
```diff
+  worker:
+    build:
+      context: .
+      dockerfile: Dockerfile.worker
+    container_name: cxkyc_worker
+    depends_on:
+      postgres: { condition: service_healthy }
+      redis: { condition: service_healthy }
+    environment:
+      - DATABASE_URL=postgresql+asyncpg://cxkyc:${POSTGRES_PASSWORD}@postgres:5432/cxkyc
+      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
+    restart: unless-stopped
```
`backend` no longer needs write access to run ingestion — it only serves API
requests and publishes/reads via Postgres + Redis.

---

### Phase 4 — Vector store (0.5–1.5 days depending on path)

`knowledge/store.py:9` uses `chromadb.PersistentClient(path=DB_PATH)` writing
to local disk under `data/chroma`. Two options:

- **Recommended: pgvector.** Since you're already moving to Postgres, add the
  `pgvector` extension (`CREATE EXTENSION vector;`), store embeddings in a
  Postgres table, and swap `knowledge/store.py`'s Chroma calls for
  SQLAlchemy + `pgvector.sqlalchemy.Vector`. One fewer moving part, one backup
  target, transactional consistency with the rest of the KYC data.
- **Alternative: standalone Chroma server.** Run `chromadb/chroma` as its own
  container (`chromadb.HttpClient(host="chroma", port=8000)` instead of
  `PersistentClient`) with a named volume. Less code change, but yet another
  stateful service to back up and scale independently — only worth it if the
  embedding workload genuinely outgrows what pgvector handles well (very large
  corpora, specialized ANN index tuning).

Given the corpus sizes implied by `data/eurlex`, `data/gdpr_text`,
`data/privacy_qa` (regulatory text, not web-scale), pgvector is almost
certainly sufficient and simpler operationally.

---

### Phase 5 — Load balancer + stateless web tier (1 day)

With Phases 1–3 done, the web tier has no local state left, so this phase is
mostly infrastructure config, not code.

**5.1 — Nginx as LB in front of N backend replicas** (or swap for Traefik if
you want automatic service discovery + Let's Encrypt — recommended once you
have a real domain). Minimal Nginx upstream, replacing the single-target
`proxy_pass` in `frontend/nginx.conf`:

```diff
+upstream backend_pool {
+    least_conn;
+    server backend1:8000 max_fails=3 fail_timeout=10s;
+    server backend2:8000 max_fails=3 fail_timeout=10s;
+    server backend3:8000 max_fails=3 fail_timeout=10s;
+}
+
 server {
     listen 80;
     ...
     location /api {
-        proxy_pass http://backend:8000;
+        proxy_pass http://backend_pool;
+        proxy_read_timeout 65s;   # SSE stream needs a long read timeout, not the 60s default
+        proxy_buffering off;      # required for SSE — Nginx must not buffer the event stream
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto $scheme;
     }
```

`proxy_buffering off` matters specifically here because `app/api/sse.py`
already sets `X-Accel-Buffering: no` for exactly this reason — Nginx needs the
matching directive or the SSE heartbeat/streaming will get buffered and the
browser will see nothing until the buffer flushes.

**5.2 — `docker-compose.yml` → replica count.** Compose's `deploy.replicas`
only takes effect under `docker stack deploy` (Swarm mode), not plain
`docker-compose up`. For plain Compose, use `docker-compose up --scale
backend=3` with explicit container names removed (`container_name:` conflicts
with scaling — drop it for the `backend` service once you scale).

For real production, prefer **Kubernetes** or **Docker Swarm** over scaled
Compose — Compose scaling has no real health-check-driven rescheduling. A
minimal K8s path:
- `Deployment` for `backend` (3+ replicas, readiness probe hitting
  `/api/v1/health/ready`, liveness probe hitting `/api/v1/health/live`)
- `Deployment` for `worker` (1–2 replicas, leader-lock protected as in Phase 3)
- `StatefulSet` or managed service for Postgres and Redis (strongly prefer
  managed: RDS/Cloud SQL for Postgres, ElastiCache/Memorystore for Redis — self
  -hosting stateful services in K8s is its own project)
- `HorizontalPodAutoscaler` on the backend Deployment, targeting CPU or a
  custom metric (request latency, queue depth)
- `Ingress` (nginx-ingress or Traefik) for TLS + routing, replacing the
  hand-rolled `frontend/nginx.conf` proxy

---

### Phase 6 — Real authentication & secrets (1–1.5 days)

- `app/api/deps.py:25`'s `get_current_user_id()` returns a hardcoded
  `SYSTEM_USER_ID`. Replace with real JWT verification using
  `jwt_secret_key`/`jwt_algorithm`/`access_token_expire_minutes` (already in
  `app/config.py:18-20`, currently unused) — add `python-jose[cryptography]`
  or `pyjwt`, a login endpoint issuing tokens, and a `Depends(get_current_user_id)`
  that decodes `Authorization: Bearer <token>` and raises `401` on failure.
- Move all secrets (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
  `GOOGLE_API_KEY`) out of `.env` files committed anywhere near the repo and
  into a secrets manager (Docker/K8s secrets at minimum; AWS Secrets Manager /
  Vault for real production). `.env.example` stays as documentation only.
- Tighten `cors_origins` (`app/config.py:22`) per environment — the current
  default `http://localhost:5173` is fine for dev but must be the real
  frontend origin(s) in prod, not `*`.

---

### Phase 7 — Observability (1 day)

- Wire the already-present `otel_exporter_otlp_endpoint` (`app/config.py:35`)
  to an actual OTel SDK setup in `app/main.py` — traces, and correlate them
  with the `X-Trace-Id` header already generated per-request
  (`app/main.py:67-73`) so a trace ID in a log line is clickable in Jaeger/Tempo.
- Add `prometheus-fastapi-instrumentator` for request-latency/error-rate
  metrics, scraped by Prometheus, visualized in Grafana.
- Ship container logs (stdout/stderr, already how `uvicorn` logs) to Loki or
  equivalent — no code change needed, just log-driver config in
  `docker-compose.yml` / K8s.
- Add Redis + Postgres exporters (`redis_exporter`, `postgres_exporter`) so
  connection-pool exhaustion and cache hit-rate (`LocalMemoryCache`/`RedisCache`
  already track `hits`/`misses` in `CacheStats`) are visible on dashboards.

---

### Phase 8 — CI/CD (1 day)

- GitHub Actions workflow: on PR, run `tests/` (pytest) against an ephemeral
  Postgres + Redis service container (GitHub Actions `services:` block) instead
  of SQLite, so tests run against the real production datastore.
- On merge to `main`: build + push `backend`, `worker`, `frontend` images to a
  registry (GHCR/ECR), tag by git SHA, run `alembic upgrade head` as a release
  step before rolling the new backend/worker images out.
- Rolling deploy (K8s `Deployment` default strategy, or `docker service update`
  under Swarm) so there's no downtime window.

---

### Phase 9 — Data protection

- Automated Postgres backups (managed service's built-in snapshotting, or
  `pg_dump` on a schedule to object storage) with a tested restore procedure.
- Move large/append-only artifacts (generated SAR PDFs, raw ingestion datasets
  currently under `data/`) to S3-compatible object storage rather than
  container-local disk or bind mounts — bind-mounting `./data` (current
  `docker-compose.yml:9-10`) doesn't work at all once you have multiple
  backend hosts.
- Redis persistence: `--appendonly yes` (already in the Phase 2 compose
  snippet) is enough for it to survive restarts as a cache; it is **not** a
  system of record, so nothing that must survive a Redis flush should live
  only in Redis (the design already respects this: cache is a performance
  optimization, not a data store).

## 4. Suggested order & rough timeline

| Phase | Depends on | Effort |
|---|---|---|
| 0. Guardrails | — | 0.5 day |
| 1. Postgres + Alembic | 0 | 1.5–2 days |
| 2. Redis cache + broker + rate limit | 1 | 1–1.5 days |
| 3. Extract workers + leader lock | 1, 2 | 1.5 days |
| 4. Vector store (pgvector) | 1 | 0.5–1.5 days |
| 5. Load balancer + horizontal scaling | 2, 3 | 1 day |
| 6. Auth & secrets | — (parallelizable) | 1–1.5 days |
| 7. Observability | 5 | 1 day |
| 8. CI/CD | 1–5 | 1 day |
| 9. Backups/data protection | 1, 4 | 0.5 day |

**Total: roughly 2–2.5 engineer-weeks** for a single engineer taking it
sequentially; phases 4, 6, and parts of 7 can run in parallel with a second
engineer to compress the timeline.

## 5. What you get at the end

- Any number of stateless `backend` replicas behind a load balancer, safely
  scalable up/down based on traffic.
- Exactly one active ingestion/agent worker at a time (HA via leader lock, not
  duplicate processing).
- Postgres as the single transactional system of record, with migrations under
  version control.
- Redis as the shared cache + real-time event bus, so the SSE alert feed works
  correctly no matter which replica a browser tab is connected to.
- Real auth, rate limiting, and secrets hygiene.
- Metrics/traces/logs correlated by trace ID across every service.

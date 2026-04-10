# Scaling & High Availability

This guide covers scaling strategies for deploying XCore in production environments with high availability.

## Overview

XCore supports several deployment modes to meet varying scale requirements:

-   **Single Instance**: Development and small workloads.
-   **Multi-Instance**: Horizontal scaling with a load balancer.
-   **Cluster Mode**: Multiple nodes with shared coordination (via Redis).

## Scaling Architecture

```text
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (Nginx/HAProxy)│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ XCore 1 │         │ XCore 2 │         │ XCore 3 │
   │         │         │         │         │         │
   │ Plugins │         │ Plugins │         │ Plugins │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Redis Cluster │
                    │  (Cache + Queue) │
                    └─────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │ PostgreSQL  │ │ PostgreSQL  │ │ PostgreSQL  │
       │   Primary   │ │   Replica   │ │   Replica   │
       └─────────────┘ └─────────────┘ └─────────────┘
```

## Multi-Instance Configuration

### 1. Load Balancer (Nginx)

```nginx
upstream xcore_backend {
    least_conn;  # Load balance by connection count
    server 192.168.1.10:8080 weight=5;
    server 192.168.1.11:8080 weight=5;
    server 192.168.1.12:8080 weight=5 backup;
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://xcore_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

### 2. Redis Cluster Configuration

```yaml
# xcore.yaml
services:
  cache:
    backend: redis
    url: "redis://redis-cluster:6379"
    cluster:
      enabled: true
      nodes:
        - "redis://192.168.1.20:6379"
        - "redis://192.168.1.21:6379"

  scheduler:
    enabled: true
    backend: redis
    url: "redis://redis-cluster:6379"
```

### 3. Database with Replication

```yaml
services:
  databases:
    primary:
      type: postgresql
      url: "${DATABASE_PRIMARY_URL}"
      pool_size: 20

    replica1:
      type: postgresql
      url: "${DATABASE_REPLICA1_URL}"
      pool_size: 10
      read_only: true
```

## Session & State Distribution

### External Sessions

To ensure "statelessness", always store user sessions and shared state in an external cache (Redis) rather than in memory.

```python
class SessionManager(TrustedBase):
    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    async def get_session(self, session_id: str) -> dict | None:
        # Sessions are shared across all XCore instances via Redis
        return await self.cache.get(f"session:{session_id}")
```

## Distributed Rate Limiting

By using the Redis cache backend, XCore's built-in rate limiter becomes distributed automatically across all running instances.

```yaml
# plugin.yaml
resources:
  rate_limit:
    calls: 100
    period_seconds: 60
```
*Note: This limit applies globally across all instances.*

## Best Practices

1.  **Stateless Design**: Never store state locally in a plugin; use Redis or a Database.
2.  **Graceful Shutdown**: Always handle `SIGTERM` to allow tasks to complete before an instance stops.
3.  **Circuit Breaker**: Use circuit breakers when calling external APIs to prevent cascading failures.
4.  **Auto-Scaling**: Use metrics (CPU/RAM/Request Rate) to scale instances automatically in Kubernetes or AWS.
5.  **Database Connection Pooling**: Configure appropriate pool sizes for each instance to avoid overwhelming the database.

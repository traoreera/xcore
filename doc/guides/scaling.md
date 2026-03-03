# Scaling et Haute Disponibilité

Ce guide couvre les stratégies de scaling pour déployer XCore en production avec haute disponibilité.

## Vue d'ensemble

XCore supporte plusieurs modes de déploiement :

- **Single Instance** — Développement et petites charges
- **Multi-Instance** — Scaling horizontal avec load balancer
- **Cluster Mode** — Plusieurs nœuds avec coordination

## Architecture de Scaling

```
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

## Configuration Multi-Instance

### 1. Load Balancer (Nginx)

```nginx
# /etc/nginx/conf.d/xcore.conf
upstream xcore_backend {
    least_conn;  # Load balancing par connexion

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
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://xcore_backend/health;
        access_log off;
    }
}
```

### 2. Configuration Redis Cluster

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
        - "redis://192.168.1.22:6379"
      options:
        max_redirects: 5
        skip_full_coverage_check: false

  scheduler:
    enabled: true
    backend: redis
    url: "redis://redis-cluster:6379"
    job_coalesce: false
    max_instances: 3
```

### 3. Base de Données avec Réplication

```yaml
services:
  databases:
    primary:
      type: postgresql
      url: "${DATABASE_PRIMARY_URL}"
      pool_size: 20
      max_overflow: 10

    replica1:
      type: postgresql
      url: "${DATABASE_REPLICA1_URL}"
      pool_size: 10
      read_only: true

    replica2:
      type: postgresql
      url: "${DATABASE_REPLICA2_URL}"
      pool_size: 10
      read_only: true
```

## Session Distribution

### Sessions Redis

```python
# Configuration des sessions distribuées
# xcore.yaml
plugins:
  session_manager:
    backend: redis
    redis_url: "${REDIS_URL}"
    key_prefix: "session:"
    ttl: 3600  # 1 heure
```

### Plugin de Session

```python
# plugins/session_manager/main.py
from xcore.sdk import TrustedBase, ok
import json


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")
        self.prefix = self.config.get("key_prefix", "session:")
        self.ttl = self.config.get("ttl", 3600)

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "get_session":
            session_id = payload["session_id"]
            data = await self.cache.get(f"{self.prefix}{session_id}")
            return ok(session=json.loads(data) if data else None)

        if action == "set_session":
            session_id = payload["session_id"]
            data = payload["data"]
            await self.cache.set(
                f"{self.prefix}{session_id}",
                json.dumps(data),
                ttl=self.ttl
            )
            return ok(saved=True)

        if action == "delete_session":
            session_id = payload["session_id"]
            await self.cache.delete(f"{self.prefix}{session_id}")
            return ok(deleted=True)

        return ok()
```

## Task Queue Distribuée

### Configuration Celery avec Redis

```python
# myapp/tasks/celery_config.py
from celery import Celery

app = Celery("xcore")
app.conf.update(
    broker_url="redis://redis-cluster:6379/0",
    result_backend="redis://redis-cluster:6379/1",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configuration du worker
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
```

### Service de Queue

```python
# myapp/services/task_queue.py
from xcore.services.base import BaseService, ServiceStatus
from celery import Celery


class TaskQueueService(BaseService):
    """Service de task queue avec Celery."""

    name = "task_queue"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.broker_url = config["broker_url"]
        self.backend_url = config["backend_url"]
        self._app = None

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        self._app = Celery("xcore")
        self._app.conf.update(
            broker_url=self.broker_url,
            result_backend=self.backend_url,
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
        )

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            # Vérifier la connexion au broker
            conn = self._app.connection()
            conn.ensure_connection(max_retries=1)
            return True, "Broker connection OK"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "broker": self.broker_url,
        }

    def send_task(self, name: str, args: tuple = (), kwargs: dict = None, queue: str = "default") -> str:
        """Envoyer une tâche."""
        result = self._app.send_task(
            name,
            args=args,
            kwargs=kwargs or {},
            queue=queue
        )
        return result.id

    def get_result(self, task_id: str, timeout: int = 10):
        """Récupérer le résultat d'une tâche."""
        result = self._app.AsyncResult(task_id)
        return result.get(timeout=timeout)
```

## Load Balancing avec Health Checks

### Plugin de Health Check Distribué

```python
# plugins/health_monitor/main.py
from xcore.sdk import TrustedBase, ok
import asyncio
import time


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")
        self.instance_id = self._generate_instance_id()
        self.heartbeat_task = None

    async def on_unload(self) -> None:
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

    def _generate_instance_id(self) -> str:
        import uuid
        return f"xcore-{uuid.uuid4().hex[:8]}"

    async def _heartbeat_loop(self):
        """Envoyer un heartbeat périodiquement."""
        while True:
            try:
                await self.cache.set(
                    f"health:{self.instance_id}",
                    {
                        "timestamp": time.time(),
                        "status": "healthy",
                        "load": self._get_load()
                    },
                    ttl=30
                )
            except Exception as e:
                print(f"Heartbeat error: {e}")

            await asyncio.sleep(10)

    def _get_load(self) -> dict:
        import psutil
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }

    def get_router(self):
        from fastapi import APIRouter

        router = APIRouter()

        @router.get("/cluster/health")
        async def cluster_health():
            """État de santé de tout le cluster."""
            # Récupérer tous les heartbeats
            keys = await self.cache.keys("health:*")
            instances = []

            for key in keys:
                data = await self.cache.get(key)
                if data:
                    instance_id = key.split(":")[1]
                    instances.append({
                        "instance_id": instance_id,
                        **data
                    })

            # Vérifier les instances manquantes
            now = time.time()
            healthy = [i for i in instances if now - i["timestamp"] < 30]

            return {
                "total_instances": len(instances),
                "healthy_instances": len(healthy),
                "instances": healthy
            }

        return router
```

## Rate Limiting Distribué

### Rate Limiter avec Redis

```python
# plugins/rate_limiter/main.py
from xcore.sdk import TrustedBase, ok
import time


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, dict]:
        """Vérifier si une requête respecte le rate limit."""
        now = int(time.time())
        window_start = now - (now % window)
        cache_key = f"ratelimit:{key}:{window_start}"

        # Incrémenter le compteur
        current = await self.cache.increment(cache_key, 1)

        # Définir l'expiration si nouvelle fenêtre
        if current == 1:
            await self.cache.expire(cache_key, window)

        remaining = max(0, limit - current)
        reset_time = window_start + window

        return (
            current <= limit,
            {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
                "current": current
            }
        )

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "check":
            allowed, info = await self.check_rate_limit(
                payload["key"],
                payload["limit"],
                payload["window"]
            )
            return ok(allowed=allowed, **info)

        return ok()
```

## Circuit Breaker

### Pattern Circuit Breaker

```python
# myapp/utils/circuit_breaker.py
from enum import Enum
import time
import asyncio
from typing import Callable


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern pour la résilience."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Vérifier si on peut passer en half-open
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    async def call(self, func: Callable, *args, **kwargs):
        """Appeler une fonction avec circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen(f"Circuit {self.name} half-open limit reached")
            self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._reset()
        else:
            self._failure_count = 0

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def _reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0


class CircuitBreakerOpen(Exception):
    pass
```

### Utilisation dans un Plugin

```python
from xcore.sdk import TrustedBase, ok
from myapp.utils.circuit_breaker import CircuitBreaker
import httpx


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Circuit breaker pour l'API externe
        self.api_breaker = CircuitBreaker(
            name="external_api",
            failure_threshold=3,
            recovery_timeout=30.0
        )

    async def call_external_api(self, endpoint: str):
        """Appeler l'API externe avec circuit breaker."""
        async def _call():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.example.com/{endpoint}",
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json()

        return await self.api_breaker.call(_call)
```

## Auto-Scaling

### Métriques de Scaling

```python
# plugins/scaling_controller/main.py
from xcore.sdk import TrustedBase, ok
import asyncio
import time


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")
        self.metrics_key = "scaling:metrics"

    def get_router(self):
        from fastapi import APIRouter
        import psutil

        router = APIRouter()

        @router.get("/metrics/scaling")
        async def scaling_metrics():
            """Métriques pour l'auto-scaling."""
            return {
                "timestamp": time.time(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "percent": psutil.virtual_memory().percent,
                    "available_mb": psutil.virtual_memory().available // 1024 // 1024,
                },
                "disk": {
                    "percent": psutil.disk_usage("/").percent,
                },
                "connections": len(psutil.net_connections()),
                "load_average": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
            }

        @router.post("/metrics/report")
        async def report_metrics():
            """Rapporter les métriques pour agrégation."""
            import socket

            hostname = socket.gethostname()
            metrics = {
                "timestamp": time.time(),
                "hostname": hostname,
                "cpu": psutil.cpu_percent(),
                "memory": psutil.virtual_memory().percent,
            }

            # Stocker dans Redis pour agrégation
            await self.cache.set(
                f"{self.metrics_key}:{hostname}",
                metrics,
                ttl=60
            )

            return ok(reported=True)

        return router
```

## Déploiement Kubernetes

### Deployment

```yaml
# k8s/xcore-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xcore
  labels:
    app: xcore
spec:
  replicas: 3
  selector:
    matchLabels:
      app: xcore
  template:
    metadata:
      labels:
        app: xcore
    spec:
      containers:
        - name: xcore
          image: xcore:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: redis-url
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: xcore
spec:
  selector:
    app: xcore
  ports:
    - port: 80
      targetPort: 8080
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xcore-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: xcore
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

## Bonnes Pratiques

1. **Stateless Design** — Ne stockez pas d'état local dans les plugins
2. **Session Externe** — Utilisez Redis pour les sessions
3. **Health Checks** — Implémentez des health checks complets
4. **Graceful Shutdown** — Gérez les signaux SIGTERM proprement
5. **Circuit Breaker** — Protégez vos appels externes
6. **Timeouts** — Définissez toujours des timeouts
7. **Retry Logic** — Implémentez le retry avec backoff

```python
class ResilientPlugin(TrustedBase):
    """Plugin résilient pour production."""

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")
        self.db = self.get_service("db")

        # Circuit breakers
        self.breakers = {
            "api": CircuitBreaker("api", failure_threshold=5),
            "db": CircuitBreaker("db", failure_threshold=3),
        }

    async def resilient_operation(self, key: str):
        """Opération avec retry et circuit breaker."""
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
        async def _operation():
            return await self.breakers["api"].call(
                self._call_external_api,
                key
            )

        try:
            return await _operation()
        except CircuitBreakerOpen:
            # Fallback vers cache
            cached = await self.cache.get(f"fallback:{key}")
            if cached:
                return cached
            raise
```

## Next Steps

- [Creating Services](./creating-services.md) — Créer des services scalables
- [Monitoring](./monitoring.md) — Observer le cluster
- [Deployment](../deployment/guide.md) — Déploiement en production

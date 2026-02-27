# Deployment Guide

Deploying XCore to production environments.

## Overview

This guide covers:
- Production configuration
- Docker deployment
- Kubernetes deployment
- Reverse proxy setup
- Monitoring and logging
- Backup and recovery

## Production Configuration

### Minimal Production Config

```yaml
# production.yaml
app:
  name: my-app
  env: production
  debug: false
  secret_key: ${APP_SECRET_KEY}
  plugin_prefix: "/api/v1/plugins"

plugins:
  directory: ./plugins
  secret_key: ${PLUGIN_SECRET_KEY}
  strict_trusted: true
  interval: 0  # Disable hot reload

services:
  databases:
    default:
      type: postgresql
      url: ${DATABASE_URL}
      pool_size: 20
      max_overflow: 10
      pool_pre_ping: true

  cache:
    backend: redis
    url: ${REDIS_URL}
    ttl: 300

  scheduler:
    enabled: true
    backend: redis
    url: ${REDIS_URL}

observability:
  logging:
    level: WARNING
    file: /var/log/xcore/app.log
    max_bytes: 52428800
    backup_count: 10

  metrics:
    enabled: true
    backend: prometheus
```

### Environment Variables

```bash
# .env.production
APP_SECRET_KEY=$(openssl rand -hex 32)
PLUGIN_SECRET_KEY=$(openssl rand -hex 32)

DATABASE_URL=postgresql://xcore:${DB_PASSWORD}@postgres:5432/xcore
DATABASE_ASYNC_URL=postgresql+asyncpg://xcore:${DB_PASSWORD}@postgres:5432/xcore
REDIS_URL=redis://:redis_password@redis:6379/0

# Optional
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

## Docker Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 xcore && \
    chown -R xcore:xcore /app

USER xcore

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health')"

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - XCORE_CONFIG=production.yaml
      - APP_SECRET_KEY=${APP_SECRET_KEY}
      - PLUGIN_SECRET_KEY=${PLUGIN_SECRET_KEY}
      - DATABASE_URL=postgresql://xcore:${DB_PASSWORD}@postgres:5432/xcore
      - REDIS_URL=redis://:redis_password@redis:6379/0
    volumes:
      - ./plugins:/app/plugins:ro
      - app_logs:/var/log/xcore
    depends_on:
      - postgres
      - redis
    networks:
      - xcore
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=xcore
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=xcore
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - xcore
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass redis_password
    volumes:
      - redis_data:/data
    networks:
      - xcore
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    networks:
      - xcore
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  app_logs:

networks:
  xcore:
    driver: bridge
```

### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream xcore {
        server app:8080;
    }

    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.example.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        client_max_body_size 10M;

        location / {
            proxy_pass http://xcore;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        location /metrics {
            # Restrict metrics access
            allow 10.0.0.0/8;
            deny all;
            proxy_pass http://xcore/metrics;
        }
    }
}
```

## Kubernetes Deployment

### Namespace and ConfigMap

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: xcore
---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: xcore-config
  namespace: xcore
data:
  production.yaml: |
    app:
      name: xcore
      env: production
      debug: false
      plugin_prefix: "/api/v1/plugins"
    plugins:
      directory: ./plugins
      strict_trusted: true
      interval: 0
    services:
      databases:
        default:
          type: postgresql
          pool_size: 20
      cache:
        backend: redis
        ttl: 300
    observability:
      logging:
        level: WARNING
      metrics:
        enabled: true
        backend: prometheus
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: xcore-secrets
  namespace: xcore
type: Opaque
stringData:
  APP_SECRET_KEY: "replace-with-64-char-hex"
  PLUGIN_SECRET_KEY: "replace-with-64-char-hex"
  DATABASE_URL: "postgresql://xcore:password@postgres:5432/xcore"
  REDIS_URL: "redis://:password@redis:6379/0"
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xcore
  namespace: xcore
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
          image: your-registry/xcore:latest
          ports:
            - containerPort: 8080
          env:
            - name: XCORE_CONFIG
              value: "production.yaml"
            - name: APP_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: APP_SECRET_KEY
            - name: PLUGIN_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: PLUGIN_SECRET_KEY
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: DATABASE_URL
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: REDIS_URL
          volumeMounts:
            - name: config
              mountPath: /app/production.yaml
              subPath: production.yaml
            - name: plugins
              mountPath: /app/plugins
              readOnly: true
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
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
      volumes:
        - name: config
          configMap:
            name: xcore-config
        - name: plugins
          persistentVolumeClaim:
            claimName: xcore-plugins
```

### Service and Ingress

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: xcore
  namespace: xcore
spec:
  selector:
    app: xcore
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: xcore
  namespace: xcore
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt"
spec:
  tls:
    - hosts:
        - api.example.com
      secretName: xcore-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: xcore
                port:
                  number: 80
```

## Monitoring

### Prometheus Metrics

XCore exposes metrics at `/metrics`:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'xcore'
    static_configs:
      - targets: ['xcore:8080']
    metrics_path: /metrics
    scrape_interval: 15s
```

### Grafana Dashboard

Create a dashboard with these queries:

```promql
# Request rate
rate(xcore_http_requests_total[5m])

# Error rate
rate(xcore_http_requests_total{status=~"5.."}[5m])

# Plugin calls
rate(xcore_plugin_calls_total[5m])

# Plugin latency
histogram_quantile(0.95, rate(xcore_plugin_duration_seconds_bucket[5m]))
```

### Health Checks

```yaml
# k8s health probes
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
```

## Logging

### Structured Logging

```yaml
observability:
  logging:
    level: INFO
    format: json
    file: /var/log/xcore/app.log
```

### Log Aggregation

Send logs to ELK stack:

```yaml
# docker-compose.yml
services:
  app:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: localhost:24224
        tag: xcore.app
```

## Backup and Recovery

### Database Backup

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL | gzip > /backups/xcore_${DATE}.sql.gz

# Keep only last 7 days
find /backups -name "xcore_*.sql.gz" -mtime +7 -delete
```

### Plugin Backup

```bash
#!/bin/bash
# backup-plugins.sh

tar czf /backups/plugins_$(date +%Y%m%d).tar.gz ./plugins/
```

### Recovery

```bash
#!/bin/bash
# restore.sh

# Restore database
gunzip -c backup.sql.gz | psql $DATABASE_URL

# Restore plugins
tar xzf backup-plugins.tar.gz
```

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Poetry
        run: pip install poetry

      - name: Install dependencies
        run: poetry install

      - name: Run tests
        run: poetry run pytest

      - name: Build Docker image
        run: docker build -t xcore:${{ github.sha }} .

      - name: Push to registry
        run: |
          docker tag xcore:${{ github.sha }} registry/xcore:latest
          docker push registry/xcore:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/xcore xcore=registry/xcore:${{ github.sha }}
          kubectl rollout status deployment/xcore
```

## Performance Tuning

### Uvicorn Workers

```bash
# Formula: (2 * CPU cores) + 1
uvicorn app:app --workers 9
```

### Database Pool

```yaml
services:
  databases:
    default:
      pool_size: 20              # Base connections
      max_overflow: 10           # Extra connections under load
      pool_pre_ping: true        # Validate before use
      pool_recycle: 3600         # Recycle after 1 hour
```

### Redis Connection Pool

```yaml
services:
  cache:
    backend: redis
    max_connections: 50
```

## Security Hardening

### Network Policies

```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: xcore
  namespace: xcore
spec:
  podSelector:
    matchLabels:
      app: xcore
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
```

### Security Context

```yaml
# k8s security
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: xcore
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
```

## Troubleshooting

### Common Issues

**High Memory Usage**:
```bash
# Check memory usage
docker stats

# Reduce pool sizes in config
pool_size: 10
max_overflow: 5
```

**Database Connection Errors**:
```bash
# Check connection pool
xcore services status

# Increase timeouts
pool_pre_ping: true
pool_recycle: 1800
```

**Plugin Loading Failures**:
```bash
# Check plugin logs
docker logs xcore_app_1 | grep -i error

# Verify signatures
xcore plugin verify ./plugins/my_plugin
```

## Next Steps

- [Monitoring Guide](monitoring.md)
- [Security Guide](../guides/security.md)
- [Scaling Guide](scaling.md)

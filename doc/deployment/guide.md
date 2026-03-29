# Deployment Guide

This guide provides instructions and best practices for deploying XCore Framework in production environments.

## 1. Production Configuration

In production, you should use a dedicated `xcore.yaml` and environment variables for sensitive data.

### Security Checklist
-   **Disable Debug**: Set `app.debug: false`.
-   **Secure Keys**: Use strong, unique strings for `app.secret_key` and `app.server_key`.
-   **Strict Trusted Mode**: Set `plugins.strict_trusted: true` to ensure only signed plugins can run in the main process.
-   **Resource Limits**: Define strict limits for all sandboxed plugins to prevent DoS.

### Minimal `xcore.yaml` for Production
```yaml
app:
  env: production
  debug: false
  secret_key: ${XCORE_SECRET_KEY}

plugins:
  directory: "/etc/xcore/plugins"
  strict_trusted: true
  autoload: true

services:
  database:
    enabled: true
    databases:
      db:
        url: ${DATABASE_URL}
        pool_size: 20
  cache:
    backend: redis
    url: ${REDIS_URL}
```

## 2. Docker Deployment

We recommend using Docker for consistent and isolated deployments.

### Example Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for sandboxing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and dependencies
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --only main

# Copy application and plugins
COPY . .

# Run with uvicorn
CMD ["uvicorn", "app:main", "--host", "0.0.0.0", "--port", "8000"]
```

## 3. Reverse Proxy (Nginx)

Always run XCore behind a reverse proxy like Nginx or Traefik to handle SSL termination and load balancing.

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 4. Monitoring & Logging

### Structured Logs
XCore outputs logs in a structured format by default. Redirect these to a central log aggregator like ELK or Datadog.

### Prometheus Metrics
Expose the `/metrics` endpoint to monitor CPU, memory, and plugin execution times.

```yaml
observability:
  metrics:
    enabled: true
    backend: prometheus
```

## 5. Continuous Deployment

1.  **Plugin Signing**: Integrate `xcore plugin sign` into your CI/CD pipeline. Only signed plugins should be promoted to production.
2.  **Blue-Green Deployment**: Use Kubernetes or Docker Swarm to perform zero-downtime deployments by swapping containers.

## 6. Scaling

-   **Horizontal Scaling**: Run multiple instances of XCore. Use a shared Redis backend for the `cache` and `scheduler` to maintain consistency across nodes.
-   **Sandbox Workers**: If using many sandboxed plugins, ensure the host machine has enough CPU cores and RAM to handle the isolated processes.

# Guide de Déploiement

Ce guide explique comment déployer xcore en production de manière sécurisée et scalable.

## Table des Matières

1. [Prérequis](#prérequis)
2. [Configuration Production](#configuration-production)
3. [Déploiement avec Docker](#déploiement-avec-docker)
4. [Déploiement avec Systemd](#déploiement-avec-systemd)
5. [Reverse Proxy](#reverse-proxy)
6. [Base de Données Production](#base-de-données-production)
7. [Monitoring](#monitoring)
8. [Sécurité](#sécurité)

## Prérequis

### Serveur Minimum Recommandé

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| CPU | 2 cœurs | 4+ cœurs |
| RAM | 2 GB | 4+ GB |
| Disque | 20 GB SSD | 50+ GB SSD |
| OS | Ubuntu 20.04 | Ubuntu 22.04 LTS |

### Logiciels Requis

- Docker 20.10+
- Docker Compose 2.0+
- Nginx ou Traefik
- PostgreSQL 14+ ou MySQL 8+
- Redis 6+

## Configuration Production

### 1. Variables d'Environnement

Créez un fichier `.env.production` :

```bash
# Application
APP_NAME=xcore
APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING

# Sécurité
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Base de données
DATABASE_URL=postgresql://xcore:password@db:5432/xcore
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_POOL_SIZE=50

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=secure_password

# Plugins
PLUGINS_DIRECTORY=/app/plugins
AUTO_RELOAD=false

# Monitoring
ENABLE_METRICS=true
METRICS_ENDPOINT=/metrics
```

### 2. Fichier config.json Production

```json
{
  "app": {
    "name": "xcore",
    "version": "0.1.0",
    "debug": false,
    "log_level": "WARNING"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": false,
    "workers": 4
  },
  "database": {
    "url": "${DATABASE_URL}",
    "echo": false,
    "pool_size": 20,
    "max_overflow": 30
  },
  "security": {
    "jwt_secret_key": "${JWT_SECRET_KEY}",
    "jwt_algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "password_hash_algorithm": "bcrypt"
  },
  "middleware": {
    "access_control": {
      "enabled": true,
      "public_paths": [
        "/auth/login",
        "/auth/register",
        "/health",
        "/docs",
        "/openapi.json"
      ]
    }
  },
  "manager": {
    "plugins_directory": "/app/plugins",
    "auto_reload": false,
    "reload_interval": 60
  },
  "cache": {
    "enabled": true,
    "backend": "redis",
    "default_ttl": 3600
  },
  "logging": {
    "level": "WARNING",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": ["file"],
    "file_path": "/var/log/xcore/app.log",
    "max_bytes": 10485760,
    "backup_count": 5
  },
  "monitoring": {
    "enabled": true,
    "prometheus_endpoint": "/metrics"
  }
}
```

## Déploiement avec Docker

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.13-slim as builder

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Installer Poetry
RUN pip install poetry

# Copier les fichiers de dépendances
COPY pyproject.toml poetry.lock ./

# Configurer Poetry pour ne pas créer de virtualenv
RUN poetry config virtualenvs.create false

# Installer les dépendances de production
RUN poetry install --no-dev --no-interaction --no-ansi

# Stage final
FROM python:3.13-slim

WORKDIR /app

# Créer utilisateur non-root
RUN useradd -m -u 1000 xcore

# Installer les dépendances runtime
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances installées
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copier l'application
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p /app/plugins /var/log/xcore /app/data && \
    chown -R xcore:xcore /app /var/log/xcore

# Passer à l'utilisateur non-root
USER xcore

# Exposer le port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Commande de démarrage
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: xcore_app
    restart: unless-stopped
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql://xcore:${DB_PASSWORD}@db:5432/xcore
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    volumes:
      - ./plugins:/app/plugins:ro
      - ./config.json:/app/config.json:ro
      - xcore_logs:/var/log/xcore
      - xcore_data:/app/data
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    networks:
      - xcore_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  db:
    image: postgres:15-alpine
    container_name: xcore_db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=xcore
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=xcore
      - PGDATA=/var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - xcore_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U xcore"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: xcore_redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - xcore_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    container_name: xcore_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - xcore_static:/var/www/static:ro
    depends_on:
      - app
    networks:
      - xcore_network

volumes:
  postgres_data:
  redis_data:
  xcore_logs:
  xcore_data:
  xcore_static:

networks:
  xcore_network:
    driver: bridge
```

### Déploiement

```bash
# 1. Cloner le repository
git clone https://github.com/votre-repo/xcore.git
cd xcore

# 2. Créer le fichier .env
cat > .env << EOF
DB_PASSWORD=votre_mot_de_passe_securise
JWT_SECRET_KEY=$(openssl rand -hex 32)
EOF

# 3. Lancer les services
docker-compose up -d

# 4. Exécuter les migrations
docker-compose exec app alembic upgrade head

# 5. Vérifier le déploiement
curl http://localhost/health
```

## Déploiement avec Systemd

### Service Systemd

Créez `/etc/systemd/system/xcore.service` :

```ini
[Unit]
Description=xcore Application
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=exec
User=xcore
Group=xcore
WorkingDirectory=/opt/xcore
Environment=PATH=/opt/xcore/.venv/bin:/usr/local/bin:/usr/bin
Environment=APP_ENV=production
Environment=PYTHONPATH=/opt/xcore
ExecStart=/opt/xcore/.venv/bin/gunicorn main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile /var/log/xcore/access.log \
    --error-logfile /var/log/xcore/error.log \
    --capture-output \
    --enable-stdio-inheritance
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Commandes Systemd

```bash
# Activer le service
sudo systemctl enable xcore

# Démarrer le service
sudo systemctl start xcore

# Vérifier le statut
sudo systemctl status xcore

# Voir les logs
sudo journalctl -u xcore -f

# Redémarrer après mise à jour
sudo systemctl restart xcore
```

## Reverse Proxy

### Configuration Nginx

```nginx
# /etc/nginx/sites-available/xcore
upstream xcore {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 100M;

    location / {
        proxy_pass http://xcore;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }

    location /static {
        alias /var/www/xcore/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /health {
        access_log off;
        proxy_pass http://xcore;
    }
}
```

### Configuration Traefik

```yaml
# docker-compose.traefik.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.dashboard=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik.rule=Host(`traefik.example.com`)"
      - "traefik.http.routers.traefik.service=api@internal"
      - "traefik.http.routers.traefik.middlewares=auth@file"
    networks:
      - xcore_network

  app:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.xcore.rule=Host(`example.com`)"
      - "traefik.http.routers.xcore.entrypoints=websecure"
      - "traefik.http.routers.xcore.tls.certresolver=letsencrypt"
      - "traefik.http.services.xcore.loadbalancer.server.port=8000"

volumes:
  letsencrypt:
```

## Base de Données Production

### Configuration PostgreSQL

```sql
-- Optimisations pour xcore
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET work_mem = '10MB';
ALTER SYSTEM SET random_page_cost = 1.1;

-- Créer l'utilisateur
CREATE USER xcore WITH PASSWORD 'mot_de_passe_securise';
CREATE DATABASE xcore OWNER xcore;
GRANT ALL PRIVILEGES ON DATABASE xcore TO xcore;

-- Extensions utiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
```

### Backups Automatiques

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="xcore"

docker exec xcore_db pg_dump -U xcore $DB_NAME | gzip > "$BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz"

# Garder seulement les 7 derniers jours
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

Crontab :

```bash
# Backup quotidien à 2h du matin
0 2 * * * /opt/xcore/scripts/backup.sh
```

## Monitoring

### Prometheus Metrics

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Métriques personnalisées
request_count = Counter('xcore_requests_total', 'Total requests', ['method', 'endpoint'])
request_duration = Histogram('xcore_request_duration_seconds', 'Request duration')
db_query_duration = Histogram('xcore_db_query_duration_seconds', 'DB query duration')

@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

### Health Checks

```python
# monitoring/health.py
from fastapi import APIRouter, status
from sqlalchemy import text
from database import get_db

router = APIRouter(tags=["monitoring"])

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {
        "database": await check_database(db),
        "redis": await check_redis(),
        "disk": check_disk_space(),
    }

    healthy = all(checks.values())
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        },
        status_code=status_code
    )

async def check_database(db: AsyncSession):
    try:
        await db.execute(text("SELECT 1"))
        return True
    except:
        return False
```

### Grafana Dashboard

Exporter les métriques Prometheus vers Grafana pour visualisation.

## Sécurité

### Checklist Sécurité

- [ ] JWT secret fort (32+ caractères)
- [ ] HTTPS activé
- [ ] Headers de sécurité configurés
- [ ] Rate limiting activé
- [ ] Logs d'audit configurés
- [ ] Mises à jour de sécurité automatiques
- [ ] Firewall configuré (ufw)
- [ ] Fail2ban activé

### Headers de Sécurité

```python
# middleware/security.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com"]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Rate Limiting

```python
# middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/sensitive")
@limiter.limit("5/minute")
async def sensitive_endpoint(request: Request):
    return {"data": "sensitive"}
```

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  app:
    deploy:
      replicas: 3
    environment:
      - DATABASE_URL=postgresql://xcore:password@pgbouncer:5432/xcore

  pgbouncer:
    image: pgbouncer/pgbouncer
    environment:
      DATABASES_HOST: postgres
      DATABASES_PORT: 5432
      DATABASES_DATABASE: xcore
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
```

### Load Balancing

Utilisez HAProxy ou NGINX pour répartir la charge entre les instances.

## Mise à Jour

### Procédure de Mise à Jour

```bash
# 1. Backup
./scripts/backup.sh

# 2. Pull des nouvelles versions
git pull origin main

# 3. Mettre à jour les dépendances
poetry install --no-dev

# 4. Exécuter les migrations
alembic upgrade head

# 5. Redémarrer
sudo systemctl restart xcore
```

### Zero-Downtime Deployment

Utilisez un load balancer pour basculer entre les versions sans interruption.

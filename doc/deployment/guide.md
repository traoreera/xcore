# Guide de Déploiement XCore en Production

Ce guide fournit les étapes et les bonnes pratiques pour déployer vos applications basées sur XCore dans un environnement de production sécurisé et performant.

---

## 1. Préparer l'Environnement

### Sécurisation des Clés Secrètes

En production, vous **devez** modifier les clés secrètes par défaut. XCore refusera de démarrer si ces clés sont détectées comme non modifiées.

```yaml
# xcore.yaml (Production)
app:
  env: "production"
  secret_key: "${XCORE_APP_SECRET}"      # À définir via variable d'env
  server_key: "${XCORE_SERVER_KEY}"      # À définir via variable d'env

plugins:
  secret_key: "${XCORE_PLUGIN_SECRET}"  # À définir via variable d'env
  strict_trusted: true                  # Oblige la signature des plugins Trusted
```

---

## 2. Déploiement via Docker

XCore est idéal pour un déploiement conteneurisé. Voici un exemple de `Dockerfile` optimisé pour la production.

### Dockerfile (Exemple)

```dockerfile
# Étape de construction
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-dev

# Étape finale (Image de production)
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copier le code source
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p logs plugins data

# Configuration par défaut
ENV XCORE_CONFIG=xcore.production.yaml
ENV LOG_LEVEL=INFO

# Lancer avec Gunicorn + Uvicorn
CMD ["gunicorn", "app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

---

## 3. Configuration du Serveur (Nginx/Reverse Proxy)

Il est recommandé de placer XCore derrière un reverse proxy comme **Nginx** pour gérer le SSL, le buffering et les timeouts.

### Configuration Nginx (Exemple)

```nginx
server {
    listen 80;
    server_name api.xcore.dev;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts pour les longs appels IPC de plugins
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
```

---

## 4. Stratégie de Persistance

### Bases de Données (PostgreSQL)
N'utilisez pas SQLite en production. Préférez un serveur PostgreSQL géré (ex: RDS, Cloud SQL) ou un cluster PostgreSQL.

### Cache et Bus (Redis)
Configurez un serveur Redis externe pour le cache, le scheduler et le bus d'événements afin de permettre le passage à l'échelle horizontale (Scaling).

---

## 5. Surveillance en Production (Health Checks)

Configurez votre orchestrateur de conteneurs (Kubernetes, Docker Swarm) pour utiliser l'endpoint de santé :

```yaml
# Exemple Kubernetes LivenessProbe
livenessProbe:
  httpGet:
    path: /plugin/ipc/health
    port: 8000
    httpHeaders:
      - name: X-Plugin-Key
        value: "votre-cle-secrete"
  initialDelaySeconds: 15
  periodSeconds: 30
```

---

## Bonnes Pratiques de Production

1. **Signez vos plugins Trusted** : Ne permettez jamais le chargement de code non signé sur vos serveurs de production.
2. **Utilisez le Sandboxing** : Tout plugin dont vous n'êtes pas l'auteur direct doit impérativement s'exécuter en mode `sandboxed`.
3. **Limitez les ressources** : Définissez des quotas CPU et RAM via `plugin.yaml` pour chaque plugin afin d'éviter qu'un bug ne sature tout votre cluster.
4. **Loguez dans un fichier externe** : Envoyez vos logs vers un service centralisé (ELK, Datadog, Sentry) pour une analyse post-mortem efficace.

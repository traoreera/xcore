# Guide de Déploiement

Ce guide détaille les étapes pour déployer XCore dans des environnements de production sécurisés et performants.

## Prérequis pour la Production

- **Python 3.11+**
- **Redis** (pour le cache et la coordination)
- **PostgreSQL** ou **MySQL** (pour la persistance des données)
- **Reverse Proxy** (Nginx, Traefik ou HAProxy)

## Configuration de Production

En production, vous devez utiliser un fichier de configuration dédié (ex: `xcore.prod.yaml`) et désactiver les fonctionnalités de développement.

### Exemple de configuration `xcore.prod.yaml`

```yaml
app:
  env: production
  debug: false
  secret_key: "${XCORE_SECRET_KEY}" # Utiliser une variable d'env
  plugin_dir: "/var/lib/xcore/plugins"

plugins:
  strict_trusted: true             # Signature obligatoire pour Trusted
  allow_hot_reload: false          # Désactiver en production pour la stabilité
  default_mode: sandboxed

database:
  url: "${DATABASE_URL}"
  pool_size: 20

cache:
  backend: redis
  url: "${REDIS_URL}"

logging:
  level: WARNING
  file: "/var/log/xcore/app.log"
  format: json                     # Format structuré pour ELK/Loki
```

## Déploiement avec Docker

Docker est la méthode recommandée pour garantir l'isolation et la reproductibilité.

### Dockerfile optimisé

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation de XCore et dépendances
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

# Copie de l'application
COPY . .

# Utilisateur non-root pour la sécurité
RUN useradd -m xcore && chown -R xcore /app
USER xcore

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Architecture avec Reverse Proxy (Nginx)

Il est crucial de placer XCore derrière un reverse proxy pour la gestion du SSL/TLS et la protection contre les attaques directes.

### Exemple de configuration Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name api.votre-domaine.com;

    ssl_certificate /etc/letsencrypt/live/api.votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.votre-domaine.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Buffering pour les gros payloads
        proxy_buffering on;
        proxy_buffer_size 8k;
    }
}
```

## Stratégies de Scaling

### Scaling Horizontal
Grâce à l'utilisation de Redis pour le cache et les événements, vous pouvez lancer plusieurs instances de XCore derrière un Load Balancer.

### Scaling des Plugins (Sandbox)
Pour les plugins sandboxés gourmands en ressources, vous pouvez ajuster les limites dans le manifeste :
```yaml
resources:
  max_memory_mb: 1024
  timeout_seconds: 60
```

## Monitoring et Maintenance

### Health Checks
Configurez votre orchestrateur (Kubernetes, Docker Swarm) pour interroger l'endpoint de santé :
`GET /health`

### Mise à jour des Plugins
1. Téléchargez le nouveau plugin dans le répertoire `plugins/`.
2. Utilisez la CLI pour recharger sans interruption :
   `xcore plugin reload nom_du_plugin`

### Sauvegardes
- Sauvegardez régulièrement votre base de données SQL.
- Le dossier `data/` des plugins contient les données persistantes locales et doit être inclus dans vos plans de sauvegarde.

## Sécurité Avancée

1. **Isolation Réseau** : Placez vos instances XCore dans un réseau privé, seul le reverse proxy doit être exposé.
2. **Secrets** : Utilisez un gestionnaire de secrets (HashiCorp Vault, AWS Secrets Manager) pour injecter les variables d'environnement.
3. **Audit** : Activez les journaux d'audit des permissions pour tracer les actions sensibles des plugins.

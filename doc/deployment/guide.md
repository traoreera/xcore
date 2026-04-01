# Guide de Déploiement

Ce guide détaille les étapes pour déployer XCore en production, que ce soit sur un serveur nu, via Docker ou sur Kubernetes.

## Configuration de Production

En production, il est crucial de désactiver les fonctionnalités de développement et de durcir la sécurité.

### Fichier `xcore.yaml` recommandé

```yaml
app:
  env: production
  debug: false
  secret_key: ${XCORE_SECRET_KEY}

plugins:
  directory: "/var/lib/xcore/plugins"
  strict_trusted: true  # Signature obligatoire
  interval: 0           # Pas de hot-reload en prod

services:
  databases:
    default:
      type: postgresql
      url: ${DATABASE_URL}
      pool_size: 20
  cache:
    backend: redis
    url: ${REDIS_URL}

observability:
  logging:
    level: INFO
    format: json  # Pour ELK / Loki
```

## Déploiement avec Docker

### Dockerfile optimisé

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Installation de XCore
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev

COPY . .

# Utilisateur non-root pour la sécurité
RUN useradd -m xcore
USER xcore

EXPOSE 8000

CMD ["uvicorn", "xcore.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Stratégie de Mise à Jour (CI/CD)

1. **Validation** : Exécuter `xcore plugin validate` sur tous les plugins.
2. **Scan de Sécurité** : Lancer l' `ASTScanner` sur les nouveaux plugins.
3. **Signature** : Signer les plugins trusted avec la clé de production.
4. **Déploiement Blue/Green** : XCore supporte le rechargement à chaud, mais pour une infrastructure immuable, préférez un remplacement de conteneurs.

## Sécurisation de l'Hôte

- **Sandbox** : Assurez-vous que l'utilisateur faisant tourner XCore a les permissions nécessaires pour créer des sous-processus mais des permissions restreintes sur le système de fichiers (en dehors du dossier `data/` des plugins).
- **Secrets** : Utilisez un gestionnaire de secrets (HashiCorp Vault, AWS Secrets Manager) pour injecter les variables d'environnement.

## Monitoring en Production

- **Endpoint `/health`** : À utiliser pour les Liveness/Readiness probes de Kubernetes.
- **Metrics** : Scrappez les métriques via Prometheus pour surveiller la latence des plugins.
- **Logs** : Redirigez stdout/stderr vers un collecteur de logs centralisé.

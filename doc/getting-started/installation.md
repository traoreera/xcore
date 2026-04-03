# Installation

Ce guide vous accompagne dans l'installation de XCore et la configuration de votre environnement de développement.

## Prérequis

Avant d'installer XCore, assurez-vous de disposer des éléments suivants :

- **Python 3.11** ou une version supérieure.
- **Poetry 1.7+** (gestionnaire de dépendances et d'environnements virtuels).
- **Git** (pour cloner le dépôt).
- **PostgreSQL 15+** et **Redis 7+** (recommandés pour les fonctionnalités de base de données et de cache).

### Vérification de la version de Python

```bash
python --version
# Doit afficher : Python 3.11.x ou plus
```

### Installation de Poetry

Si vous n'avez pas encore installé Poetry :

```bash
# Sur macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# Sur Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

Ajoutez Poetry à votre PATH si nécessaire :

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Étapes d'installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

### 2. Installer les dépendances

Utilisez Poetry pour installer toutes les dépendances du projet, y compris celles de développement :

```bash
poetry install
```

Cette commande va :
- Créer un environnement virtuel isolé.
- Installer les bibliothèques requises (FastAPI, SQLAlchemy, Pydantic, etc.).
- Installer les outils de développement (Pytest, Black, etc.).

### 3. Vérifier l'installation

```bash
poetry run xcore --version
# Doit afficher : xcore v2.0.0
```

## Configuration de l'environnement

### Fichier de configuration `.env`

Copiez le fichier d'exemple et générez vos clés secrètes :

```bash
cp .env.example .env
```

Modifiez le fichier `.env` pour y inclure vos paramètres :

```bash
# Clé secrète de l'application (utilisée pour signer les tokens/sessions)
APP_SECRET_KEY=votre_cle_secrete_longue_et_aleatoire

# Clé de signature des plugins (utilisée pour valider les plugins Trusted)
PLUGIN_SECRET_KEY=votre_cle_de_signature_plugin

# URLs de connexion aux services
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/xcore
REDIS_URL=redis://localhost:6379/0
```

### Référence des variables d'environnement principales

| Variable | Requis | Description |
|----------|----------|-------------|
| `APP_SECRET_KEY` | Oui | Clé de sécurité principale du framework. |
| `PLUGIN_SECRET_KEY` | Oui | Clé utilisée pour la signature cryptographique des plugins. |
| `DATABASE_URL` | Non* | URL de connexion SQLAlchemy (si le service DB est utilisé). |
| `REDIS_URL` | Non* | URL de connexion Redis (si le service de cache/scheduler est utilisé). |
| `LOG_LEVEL` | Non | Niveau de log (DEBUG, INFO, WARNING, ERROR). |

## Configuration de la Base de Données et du Cache

### Docker (Option rapide)

Si vous ne souhaitez pas installer PostgreSQL et Redis localement, vous pouvez utiliser Docker :

```bash
# Lancer PostgreSQL
docker run -d --name xcore-db -p 5432:5432 -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=xcore postgres:15

# Lancer Redis
docker run -d --name xcore-cache -p 6379:6379 redis:7-alpine
```

## Lancement en mode Développement

Pour lancer le serveur avec le rechargement à chaud (hot-reload) :

```bash
# Utilisation de la commande make (recommandé)
make run-dev

# Ou manuellement via uvicorn
poetry run uvicorn app:app --reload --port 8082
```

Le serveur sera accessible sur `http://localhost:8082`. Vous pouvez vérifier son état en consultant l'endpoint de santé :

```bash
curl http://localhost:8082/plugin/ipc/health
```

## Prochaines étapes

Maintenant que XCore est opérationnel, passez au **[Guide de démarrage rapide](quickstart.md)** pour créer votre premier plugin.

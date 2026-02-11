# Guide d'Installation

Ce guide vous accompagne dans l'installation et la configuration de xcore sur votre système.

## Prérequis

Avant d'installer xcore, assurez-vous d'avoir les éléments suivants :

### Logiciels Requis

| Logiciel | Version Minimum | Recommandé |
|----------|-----------------|------------|
| Python | 3.11 | 3.13+ |
| Poetry | 1.7.0 | Dernière version |
| Git | 2.30 | Dernière version |
| SQLite | 3.35 | 3.40+ (dev) |
| Redis | 6.0 | 7.0+ (production) |

### Environnement Système

- **OS**: Linux (Ubuntu 20.04+), macOS (12+), Windows (WSL2 recommandé)
- **Mémoire**: 2GB minimum, 4GB recommandé
- **Espace disque**: 1GB minimum

## Installation

### Étape 1: Cloner le Repository

```bash
git clone https://github.com/votre-repo/xcore.git
cd xcore
```

### Étape 2: Installer les Dépendances avec Poetry

Poetry est le gestionnaire de dépendances recommandé pour xcore.

```bash
# Vérifier que Poetry est installé
poetry --version

# Installer les dépendances
poetry install

# Activer l'environnement virtuel
poetry shell
```

### Étape 3: Configuration de la Base de Données

#### Option A: SQLite (Développement)

Par défaut, xcore utilise SQLite. Créez le fichier de configuration :

```bash
# La configuration par défaut utilise SQLite
# Voir config.json pour modifier
```

#### Option B: MySQL (Production)

Pour utiliser MySQL, modifiez le fichier `config.json` :

```json
{
  "database": {
    "driver": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "xcore",
    "username": "xcore_user",
    "password": "votre_mot_de_passe"
  }
}
```

Puis créez la base de données MySQL :

```bash
mysql -u root -p
CREATE DATABASE xcore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'xcore_user'@'localhost' IDENTIFIED BY 'votre_mot_de_passe';
GRANT ALL PRIVILEGES ON xcore.* TO 'xcore_user'@'localhost';
FLUSH PRIVILEGES;
```

### Étape 4: Configuration de Redis (Optionnel)

Pour le cache et les sessions, configurez Redis dans `config.json` :

```json
{
  "redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": null,
    "ttl": 3600
  }
}
```

### Étape 5: Initialisation de la Base de Données

```bash
# Exécuter les migrations Alembic
alembic upgrade head

# Ou utiliser le script de migration automatique
python -m tools.auto_migrate
```

### Étape 6: Création du Super Administrateur

```bash
# Le super admin est automatiquement créé au premier démarrage
# Email: root@system.local
# Mot de passe: Root@123

# Pour créer manuellement un admin
python -m auth.init_root
```

### Étape 7: Lancer l'Application

```bash
# Mode développement avec rechargement automatique
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Mode production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration Avancée

### Variables d'Environnement

Créez un fichier `.env` à la racine du projet :

```bash
# Application
APP_NAME=xcore
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# Sécurité
JWT_SECRET_KEY=votre-cle-secrete-tres-longue-et-aleatoire
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Base de données
DATABASE_URL=sqlite:///./app.db
# ou pour MySQL
# DATABASE_URL=mysql+mysqlconnector://user:pass@localhost/xcore

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (optionnel)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-mot-de-passe-app
```

### Fichier config.json

Le fichier `config.json` centralise toute la configuration :

```json
{
  "app": {
    "name": "xcore",
    "version": "0.1.0",
    "description": "Framework ERP Multi-Plugins",
    "debug": false
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": true,
    "workers": 1
  },
  "database": {
    "url": "sqlite:///./app.db",
    "echo": false,
    "pool_size": 5,
    "max_overflow": 10
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
      "public_paths": ["/auth/login", "/auth/register", "/docs", "/openapi.json"]
    }
  },
  "manager": {
    "plugins_directory": "./plugins",
    "auto_reload": true,
    "reload_interval": 2
  },
  "cache": {
    "enabled": true,
    "backend": "redis",
    "default_ttl": 3600
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": ["console", "file"],
    "file_path": "logs/app.log"
  }
}
```

## Vérification de l'Installation

### Test de l'API

```bash
# Vérifier que l'API est accessible
curl http://localhost:8000/health

# Obtenir un token d'authentification
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=root@system.local&password=Root@123"
```

### Interface de Documentation

Accédez aux interfaces de documentation automatique :

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Dépannage

### Problèmes Courants

#### Poetry non trouvé

```bash
# Installer Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Ajouter au PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Erreur de connexion à la base de données

```bash
# Vérifier la configuration
cat config.json | grep -A 5 database

# Pour SQLite, vérifier les permissions
touch app.db
chmod 644 app.db
```

#### Erreur Redis

```bash
# Démarrer Redis
sudo systemctl start redis

# Vérifier le statut
redis-cli ping
```

#### Port déjà utilisé

```bash
# Trouver le processus utilisant le port 8000
lsof -i :8000

# Utiliser un autre port
uvicorn main:app --port 8001
```

### Logs et Debug

Les logs sont stockés dans `logs/app.log` :

```bash
# Suivre les logs en temps réel
tail -f logs/app.log

# Niveau de log DEBUG
LOG_LEVEL=DEBUG uvicorn main:app --reload
```

## Mise à Jour

```bash
# Récupérer les dernières modifications
git pull origin main

# Mettre à jour les dépendances
poetry update

# Exécuter les migrations
alembic upgrade head
```

## Prochaines Étapes

Maintenant que xcore est installé, consultez :

- [Quick Start](quickstart.md) - Premier pas avec xcore
- [Créer un Plugin](tutorials/create-plugin.md) - Développer votre premier plugin
- [Configuration](configurations.md) - Configuration avancée
- [API Reference](api/endpoints.md) - Documentation des endpoints

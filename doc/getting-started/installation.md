# Installation de XCore

Ce guide vous accompagne dans l'installation de XCore et la configuration de votre environnement de développement.

## Prérequis

Avant de commencer, assurez-vous d'avoir :

- **Python 3.10** ou supérieur.
- **Poetry** (recommandé pour la gestion des dépendances).
- **Git** (pour cloner le dépôt).
- Une instance de **PostgreSQL** et **Redis** accessible.

## Étapes d'Installation

### 1. Cloner le Dépôt

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

### 2. Installer les Dépendances

XCore utilise Poetry pour une gestion robuste des versions.

```bash
poetry install
```

Si vous préférez utiliser `pip` :
```bash
pip install .
```

### 3. Configuration de l'Environnement

Créez un fichier `.env` à la racine du projet (voir `.env.example`).

```env
XCORE_SECRET_KEY="votre_clé_secrète_très_longue"
DATABASE_URL="postgresql://user:pass@localhost:5432/xcore"
REDIS_URL="redis://localhost:6379/0"
```

## Vérification de l'Installation

Lancez le CLI pour vérifier que tout fonctionne :

```bash
poetry run xcore --version
# Devrait afficher : xcore v2.x.x
```

## Démarrage du Framework

Pour lancer le serveur de développement avec rechargement à chaud (Hot Reload) :

```bash
poetry run uvicorn xcore.api.main:app --reload
```

Le framework est maintenant prêt à accueillir vos plugins !

## Dépannage Courant

- **Erreur de connexion DB** : Vérifiez que PostgreSQL tourne et que l'URL dans `.env` est correcte.
- **Poetry introuvable** : Installez-le via `pip install poetry` et assurez-vous qu'il est dans votre PATH.
- **Sandboxing (Linux)** : Le mode sandbox nécessite des permissions pour créer des processus. Si vous êtes dans un conteneur, assurez-vous qu'il a les privilèges nécessaires.

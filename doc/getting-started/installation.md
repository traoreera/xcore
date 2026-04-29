# Installation

## Prérequis

- **Python 3.11+**
- **Poetry 2.x** ou **uv**
- **Redis 7+** (optionnel — requis uniquement si `cache.backend: redis` ou `scheduler.backend: redis`)
- **PostgreSQL 15+** / **MySQL 8+** (optionnel — SQLite fonctionne sans installation)

---

## Depuis le dépôt source

```bash
git clone https://github.com/traoreera/xcore
cd xcore

# Avec Poetry (recommandé)
poetry install

# Ou avec uv
uv sync
```

### Lancer le serveur de développement

```bash
# Via Poetry
poetry run uvicorn main:app --reload --port 8000

# Via uv
uv run uvicorn main:app --reload --port 8000
```

---

## En tant que dépendance (uv)

```bash
uv add "xcore @ git+https://github.com/traoreera/xcore"
```

---

## Variables d'environnement

XCore charge automatiquement un fichier `.env` à la racine du projet si `app.dotenv` est configuré dans `xcore.yaml`.
Toute clé de configuration peut être surchargée via une variable d'environnement au format :

```
XCORE__<SECTION>__<CLE>=valeur
```

Exemples :

```bash
XCORE__APP__DEBUG=true
XCORE__SERVICES__CACHE__BACKEND=redis
XCORE__SERVICES__CACHE__URL=redis://localhost:6379/0
```

---

## Structure minimale d'un projet

```
mon-projet/
├── xcore.yaml          # Configuration principale
├── main.py             # Point d'entrée FastAPI
└── plugins/
    └── mon_plugin/
        ├── plugin.yaml
        └── src/
            └── main.py
```

---

## Vérifier l'installation

```bash
poetry run xcore --version
# xcore v2.1.2
```

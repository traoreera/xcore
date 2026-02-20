# Commandes et outils

xcore ne dispose pas d'une CLI dédiée, mais expose des commandes via le `Makefile` et des scripts utilitaires.

---

## Makefile

Depuis la racine du projet :

```bash
make help          # Affiche toutes les commandes disponibles
make run           # Lance le serveur en mode développement
make run-prod      # Lance le serveur en mode production
make test          # Lance la suite de tests
make lint          # Vérifie le style du code
make format        # Formate le code avec black/ruff
make migrate       # Applique les migrations Alembic
make migration     # Crée une nouvelle migration (MESSAGE=...)
make clean         # Nettoie les fichiers temporaires
```

### Exemples

```bash
# Créer une migration après modification des modèles
make migration MESSAGE="ajoute_colonne_avatar_user"

# Lancer les tests avec couverture
make test

# Lancer en production (sans reload, workers multiples)
make run-prod
```

---

## Démarrage avec uvicorn

```bash
# Développement (reload automatique)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production (workers multiples)
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000

# Avec un fichier .env
uvicorn main:app --reload --env-file .env
```

---

## Migrations Alembic

xcore utilise Alembic pour gérer les migrations de base de données.

```bash
# Créer une migration automatique (après modification des modèles)
alembic revision --autogenerate -m "description_de_la_migration"

# Appliquer toutes les migrations en attente
alembic upgrade head

# Revenir à la migration précédente
alembic downgrade -1

# Voir l'historique des migrations
alembic history

# Voir la migration actuelle
alembic current
```

> La configuration d'Alembic se trouve dans `alembic.ini`.

---

## Scripts utilitaires (`manager/tools/`)

Le dossier `manager/tools/` contient des scripts pour la gestion de la base de données et des plugins.

```bash
# Initialiser la base de données (créer les tables)
poetry run python manager/tools/init_db.py

# Créer un utilisateur admin
poetry run python manager/tools/create_admin.py \
  --email admin@example.com \
  --password monmotdepasse

# Lister les plugins découverts
poetry run python manager/tools/list_plugins.py

# Valider un plugin avant installation
poetry run python manager/tools/validate_plugin.py plugins/mon_plugin/
```

---

## Poetry

xcore utilise Poetry pour la gestion des dépendances.

```bash
# Installer les dépendances
poetry install

# Ajouter une dépendance
poetry add nom-du-package

# Ajouter une dépendance de développement
poetry add --group dev nom-du-package

# Mettre à jour les dépendances
poetry update

# Activer l'environnement virtuel
poetry shell

# Exécuter une commande dans l'environnement
poetry run python script.py
```

---

## Variables d'environnement utiles

```bash
# Mode debug
export DEBUG=true

# Désactiver le cache pour les tests
export CACHE_ENABLED=false

# Pointer vers une DB de test
export DATABASE_URL=sqlite:///./test.db
```

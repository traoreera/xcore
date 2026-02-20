# XCore Framework

XCore est un framework d'orchestration modulaire basé sur **FastAPI**, conçu pour charger, isoler et gérer des plugins dans un environnement sécurisé (sandbox). Il permet de construire des applications extensibles où chaque fonctionnalité peut être développée, testée et déployée indépendamment.

## 🚀 Fonctionnalités Clés

- **Système de Plugins Dynamique** : Chargez, déchargez et appelez des plugins à chaud sans redémarrer le serveur.
- **Sandboxing & Sécurité** : Exécution isolée des plugins avec un superviseur (gestion des timeouts, redémarrages automatiques, limitation de débit).
- **Intégration de Services Native** : Support intégré pour SQL (PostgreSQL, MySQL, SQLite), NoSQL (Redis), Planification de tâches (APScheduler), et plus encore.
- **Architecture Événementielle (Hooks)** : Un gestionnaire de hooks puissant permettant la communication inter-plugins et la réaction aux événements système.
- **Hot Reloading** : Surveillance automatique du dossier `plugins/` pour recharger les modifications en temps réel.
- **Génération de Documentation** : Outil intégré (`docgen`) pour agréger et générer la documentation technique du projet.
- **Prêt pour la Production** : Configuration via YAML, gestion des variables d'environnement et logs structurés.

## 🏗️ Architecture

Le projet est structuré autour de plusieurs composants fondamentaux :

- **`Manager`** (`xcore/manager.py`) : L'orchestrateur principal qui coordonne le cycle de vie des plugins et l'intégration des services.
- **`PluginManager`** (`xcore/sandbox/manager.py`) : Gère le chargement, la validation des signatures et l'exécution des plugins.
- **`Sandbox`** (`xcore/sandbox/`) : Fournit l'environnement d'isolation pour l'exécution sécurisée du code tiers.
- **`Integration`** (`xcore/integration/`) : Unifie l'accès aux services externes (bases de données, cache, scheduler) via une configuration centralisée.

## 🛠️ Installation

### Prérequis

- **Python 3.11+**
- **Poetry** (gestionnaire de dépendances)

### Étapes

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/traoreera/xcore
   cd xcore
   ```

2. **Installer les dépendances** :
   ```bash
   poetry install
   ```

3. **Configurer l'environnement** :
   Copiez le fichier d'exemple (si présent) ou créez un fichier `.env` à la racine :
   ```env
   DATABASE_URL=sqlite:///./xcore.db
   REDIS_URL=redis://localhost:6379/0
   WEBHOOK_SECRET=votre_secret_ici
   ```

4. **Lancer l'application** :
   ```bash
   poetry run uvicorn main:app --reload
   ```

## 🔌 Développement de Plugins

Chaque plugin doit résider dans le dossier `plugins/` et suivre cette structure minimale :

```
plugins/mon_plugin/
├── plugin.yaml      # Manifeste du plugihttps://github.com/traoreera/xcore/tree/featuresn (nom, version, entrées)
├── plugin.sig       # Signature de sécurité (si strict_trusted=True)
└── src/
    └── main.py      # Code source principal
```

### Exemple de `plugin.yaml` :
```yaml
name: "mon_plugin"
version: "1.0.0"
entry_point: "src.main:Plugin"
trusted: true
```

## 📜 Scripts et Commandes

XCore propose une large gamme de commandes via **Poetry** et **Make** pour faciliter le développement et l'exploitation.

### Commandes Makefile (Recommandé)

Utilisez `make help` pour voir toutes les commandes disponibles. Voici les plus courantes :

- **Développement** :
  - `make init` : Initialise le projet (installation + lancement dev).
  - `make run-dev` : Lance le serveur en mode développement (port 8082, avec reload).
  - `make run-st` : Lance le serveur en mode production/statique (port 8081).
  - `make clean` : Nettoie les fichiers temporaires et caches Python.

- **Qualité et Build** :
  - `make lint-fix` : Corrige automatiquement le formatage du code (Black, Isort, Autopep8).
  - `make build` : Exécute le nettoyage, l'installation et le linting.
  - `make test` : Lance la suite de tests unitaires.

- **Gestion des Plugins** :
  - `make add-plugin PLUGIN_NAME=nom` : Ajoute ou met à jour un plugin depuis un dépôt Git.
  - `make rm-plugin PLUGIN_NAME=nom` : Supprime un plugin.

- **Supervision et Logs** :
  - `make logs-live` : Affiche les logs en temps réel.
  - `make logs-stats` : Affiche les statistiques des logs (erreurs, warnings, etc.).
  - `make logs-health-check` : Effectue un bilan de santé complet du système via les logs.

- **Docker** :
  - `make docker-dev` : Lance l'environnement de développement via Docker Compose.
  - `make docker-prod` : Lance l'environnement de production via Docker Compose.

### Scripts Poetry (Alternatifs)

- `poetry run migrate` : Exécute les migrations de base de données.
- `poetry run auto_migrate` : Génère et applique automatiquement les migrations.
- `poetry run dbutils` : Outils de découverte de modèles.

## 📖 Documentation et Outils

XCore inclut des outils intégrés pour faciliter la maintenance et la documentation du code :

- **`docgen`** : Un moteur interne qui agrège les fichiers Markdown du dossier `docs/` et peut analyser le code source pour générer une documentation technique structurée.
- **`doc-gen-summaries.json`** : Un cache pour les résumés générés automatiquement.
- **Sphinx** : Support optionnel pour la génération de documentation HTML statique via `make auto-docs`.

Pour consulter la documentation technique existante, explorez le dossier `docs/` :
- **Configurations** : `docs/configurations/` (base, core, redis, secure...).
- **Intégration** : `docs/integration/` (config, core, services...).
- **Sandbox** : `docs/sandbox/` (manager, router, supervisor...).
- **Hooks** : `docs/hooks/`.

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

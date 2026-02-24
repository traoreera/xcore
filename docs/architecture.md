# Architecture de xcore

Cette page décrit l'architecture interne du framework, ses composants principaux et les flux de données entre eux.

---

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│              (Point d'entrée FastAPI)                   │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │       Manager        │
              │  (Orchestrateur)     │
              └──┬──────────────┬───┘
                 │              │
    ┌────────────▼───┐   ┌──────▼──────────┐
    │  PluginLoader  │   │    Scheduler     │
    │  (plManager/)  │   │  (BackgroundTask)│
    └────────────┬───┘   └─────────────────┘
                 │
    ┌────────────▼────────────────────────┐
    │              Plugins                │
    │   plugins/                          │
    │   ├── plugin_a/  (router monté)     │
    │   ├── plugin_b/  (router monté)     │
    │   └── plugin_n/  ...               │
    └─────────────────────────────────────┘
                 │
    ┌────────────▼────────────────────────┐
    │         Extensions / Services       │
    │   extensions/services/              │
    │   ├── auth/                         │
    │   ├── cache/  (Redis)               │
    │   ├── database/  (SQLAlchemy)       │
    │   └── security/  (JWT)              │
    └─────────────────────────────────────┘
```

---

## Composants principaux

### `main.py` — Point d'entrée

Initialise l'application FastAPI et délègue le montage des routes au `Manager`. C'est ici que le cycle de vie de l'application est géré (startup / shutdown).

### `manager/` — Orchestrateur

Le cœur du framework. Il contient :

- **`plManager/loader.py`** : Découverte et chargement dynamique des plugins depuis le dossier `plugins/`. Gère la purge du cache Python (`sys.modules`) pour permettre le hot reload.
- **`plManager/reloader.py`** : Surveille les changements de fichiers et déclenche un rechargement à chaud des plugins sans redémarrer le serveur.
- **`plManager/installer.py`** : Validation et installation d'un nouveau plugin (vérification de la structure, des dépendances, des métadonnées).
- **`plManager/repository.py`** : Registre des plugins actifs en mémoire et en base de données.
- **`plManager/validator.py`** : Valide qu'un plugin respecte le contrat attendu (présence de `PLUGIN_INFO`, de la classe `Plugin`, du `router`).

### `plugins/` — Plugins dynamiques

Chaque sous-dossier est un plugin indépendant. Le `Loader` les découvre automatiquement. Un plugin expose ses routes via un `APIRouter` FastAPI et déclare ses métadonnées dans `PLUGIN_INFO`.

Voir [Anatomie d'un plugin](./reference/plugin-anatomy.md) pour la structure complète.

### `extensions/services/` — Services internes

Fonctionnalités transversales partagées entre les plugins :

| Service | Rôle |
|---------|------|
| `auth/` | Authentification JWT, gestion des sessions |
| `admin/` | Rôles, permissions, utilisateurs admin |
| `cache/` | Cache Redis centralisé |
| `database/` | ORM SQLAlchemy, migrations Alembic |
| `security/` | Hachage des mots de passe, tokens |
| `otpprovider/` | Codes OTP à usage unique |
| `middleware/` | Middlewares FastAPI personnalisés |

### `loggers/` — Journalisation

Système de logs centralisé et configurable. Sortie colorée en développement, structurée en production. Chaque plugin et chaque composant core dispose de son propre logger nommé.

---

## Flux de démarrage

```
1. uvicorn démarre main.py
2. FastAPI crée l'application
3. Manager.startup() est appelé
4. PluginLoader scanne plugins/
5. Pour chaque plugin valide :
   a. Import du module Python
   b. Validation via Validator
   c. Instanciation de Plugin()
   d. Montage du router dans FastAPI
   e. Mise à jour du schéma OpenAPI
6. Scheduler démarre les tâches planifiées
7. L'API est prête à recevoir des requêtes
```

---

## Hot Reload

Quand un fichier plugin est modifié :

```
Modification détectée (Reloader)
    → Purge sys.modules pour le plugin concerné
    → Démontage du router existant de FastAPI
    → Rechargement du module Python
    → Re-validation et re-montage du router
    → Mise à jour de l'OpenAPI/Swagger
```

Ce mécanisme est isolé : un plugin défaillant n'affecte pas les autres.

---

## Isolation (Sandbox)

Chaque plugin peut être exécuté dans un environnement contrôlé avec des limites sur :

- **CPU** : temps d'exécution maximal
- **Mémoire** : quota RAM par plugin
- **Timeout** : durée maximale d'une requête

Cela protège le serveur principal contre les plugins défectueux ou malveillants.

# Configuration Globale

XCore utilise un système de configuration hiérarchique et typé. La source principale est `xcore.yaml`, mais chaque paramètre peut être surchargé par des variables d'environnement.

## Structure de `xcore.yaml`

Le fichier est divisé en sections correspondant aux composants du noyau (`XcoreConfig`).

### Section `app` (AppConfig)
Configuration générale de l'application.

- `name` : Nom de l'application (défaut: `xcore-app`).
- `env` : Environnement (`development`, `staging`, `production`).
- `debug` : Active le mode debug de FastAPI (défaut: `false`).
- `secret_key` : Clé de chiffrement (obligatoire en prod).
- `plugin_prefix` : Préfixe d'URL pour les plugins (défaut: `/plugin`).

### Section `plugins` (PluginConfig)
Configuration du `PluginSupervisor`.

- `directory` : Répertoire de scan des plugins (défaut: `./plugins`).
- `strict_trusted` : Si `true`, refuse de charger un plugin Trusted non signé.
- `interval` : Intervalle de scan pour le hot-reload (secondes).
- `entry_point` : Nom du fichier d'entrée par défaut (défaut: `src/main.py`).

### Section `services` (ServicesConfig)
Configuration des bases de données, du cache et du scheduler.

#### `databases`
Dictionnaire de configurations de bases de données (SQL ou NoSQL).
- `url` : Chaîne de connexion SQLAlchemy ou Redis.
- `pool_size` : Taille du pool de connexions (SQL).

#### `cache`
- `backend` : `memory` ou `redis`.
- `url` : Requis si backend est `redis`.
- `ttl` : Durée de vie par défaut (secondes).

### Section `observability` (ObservabilityConfig)
Journalisation, métriques et traces.

- `logging` : Niveau (`INFO`, `DEBUG`), format et fichier de sortie.
- `metrics` : Activation et backend (`prometheus`, `statsd`, `memory`).
- `tracing` : Activation et backend (`jaeger`, `opentelemetry`, `noop`).

### Section `security` (SecurityConfig)
Paramètres globaux du bac à sable.

- `allowed_imports` / `forbidden_imports` : Listes globales pour l' `ASTScanner`.
- `rate_limit_default` : Limite appliquée aux plugins ne déclarant pas la leur.

---

## Surcharge par Variables d'Environnement

Le framework supporte la surcharge dynamique via le préfixe `XCORE__` suivi du chemin de la clé en majuscules avec un double underscore (`__`) comme séparateur.

### Règles de conversion :
- Les chaînes `"true"`, `"1"`, `"yes"` deviennent `True`.
- Les chaînes `"false"`, `"0"`, `"no"` deviennent `False`.
- Les nombres sont automatiquement convertis en entiers.

### Exemples :

| Variable d'environnement | Clé YAML correspondante |
|--------------------------|-------------------------|
| `XCORE__APP__ENV` | `app.env` |
| `XCORE__SERVICES__CACHE__BACKEND` | `services.cache.backend` |
| `XCORE__SERVICES__DATABASES__DEFAULT__URL` | `services.databases.default.url` |
| `XCORE__PLUGINS__STRICT_TRUSTED` | `plugins.strict_trusted` |

---

## Le Manifeste du Plugin (`plugin.yaml`)

Chaque plugin définit ses propres métadonnées et contraintes d'exécution.

### Section `resources`
- `timeout_seconds` : Temps maximum pour un appel IPC (Sandbox).
- `max_memory_mb` : Limite mémoire via `RLIMIT_AS`.
- `rate_limit` : Bloc `calls` et `period_seconds`.

### Section `permissions`
Définit les accès autorisés ou refusés.
- `resource` : Pattern glob (ex: `cache.user_*`).
- `actions` : Liste (`read`, `write`, `execute`, `*`).
- `effect` : `allow` ou `deny`.

### Section `filesystem` (Sandbox uniquement)
- `allowed_paths` : Chemins autorisés (relatifs au plugin). Défaut : `["data/"]`.
- `denied_paths` : Chemins interdits. Défaut : `["src/"]`.

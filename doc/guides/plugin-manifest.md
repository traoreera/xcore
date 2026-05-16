# Manifeste de Plugin (plugin.yaml)

Chaque plugin est décrit par un `plugin.yaml` à la racine de son dossier. Ce fichier contrôle le mode d'exécution, les ressources, les permissions, la sécurité IPC et les métadonnées.

---

## Structure complète

```yaml
# ── Identité ──────────────────────────────────────────────────
name: my_plugin              # [obligatoire] identifiant unique (snake_case)
version: "1.0.0"             # [obligatoire] version semver
author: "Team Backend"
description: "Description courte du plugin"
framework_version: ">=2.0"   # contrainte sur xcore (défaut: >=2.0)

# ── Exécution ─────────────────────────────────────────────────
execution_mode: trusted      # trusted | sandboxed | legacy
entry_point: src/main.py     # chemin relatif vers le fichier principal

# ── Dépendances inter-plugins ─────────────────────────────────
requires:
  - billing                       # version quelconque
  - name: crm
    version: ">=1.2,<2.0"         # contrainte semver

# ── Autorisation IPC ──────────────────────────────────────────
# Liste vide ou absente = deny-by-default (tout IPC refusé)
allowed_callers:
  - billing
  - dashboard

# ── Imports Python autorisés (mode sandboxed uniquement) ──────
allowed_imports:
  - json
  - datetime
  - re

# ── Permissions (capabilities déclarées) ──────────────────────
permissions:
  - action: read
    resource: "db:orders"
  - action: write
    resource: "cache:sessions"

# ── Variables d'environnement ─────────────────────────────────
env:
  API_KEY: "${MY_API_KEY}"    # substitution depuis l'OS
  BASE_URL: "https://api.example.com"

# ── Limites de ressources ─────────────────────────────────────
resources:
  timeout_seconds: 10
  max_memory_mb: 128
  max_disk_mb: 50
  rate_limit:
    calls: 100
    period_seconds: 60

# ── Runtime ───────────────────────────────────────────────────
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 3
  retry:
    max_attempts: 1
    backoff_seconds: 0.0

# ── Filesystem (mode sandboxed) ───────────────────────────────
filesystem:
  allowed_paths:
    - "data/"
  denied_paths:
    - "src/"

# ── Configuration arbitraire ─────────────────────────────────
# Tout champ inconnu est accessible via self.manifest.extra
low_stock_threshold: 10
feature_flags:
  enable_beta: true
```

---

## Champs obligatoires

| Champ | Type | Description |
|:------|:-----|:------------|
| `name` | string | Identifiant unique (snake_case). Utilisé dans les appels IPC et le registry. |
| `version` | string | Version semver (`"1.0.0"`). |

---

## Modes d'exécution

### `trusted`

Accès complet au kernel, aux services et à l'API FastAPI. Peut appeler d'autres plugins via IPC.

**Requis :** un fichier `plugin.sig` valide.

```bash
xcore plugin sign plugins/my_plugin --key "votre_secret_key"
```

### `sandboxed`

Le code source est analysé par AST avant chargement. Seuls les imports listés dans `allowed_imports` (et `security.allowed_imports` dans `integration.yaml`) sont autorisés. S'exécute dans un sous-processus OS isolé.

```yaml
execution_mode: sandboxed
allowed_imports:
  - json
  - datetime
  - re
```

### `legacy`

Compatibilité descendante — comportement `trusted` sans vérification de signature. À éviter en production.

---

## Dépendances (`requires`)

```yaml
requires:
  - billing                    # n'importe quelle version
  - name: analytics
    version: ">=2.0,<3.0"
  - name: crm
    version: "^1.5.0"          # >=1.5.0,<2.0.0
  - name: reports
    version: "~1.2.0"          # >=1.2.0,<1.3.0
```

Opérateurs supportés : `>=`, `<=`, `>`, `<`, `==`, `!=`, `^`, `~`.

xcore vérifie les dépendances au boot et refuse le chargement si une dépendance est absente ou incompatible.

---

## Autorisation IPC (`allowed_callers`)

```yaml
# Seuls billing et dashboard peuvent appeler ce plugin via IPC
allowed_callers:
  - billing
  - dashboard
```

**Règle deny-by-default :** si `allowed_callers` est absent ou vide, tout appel IPC est refusé. Les appels HTTP directs ne sont jamais filtrés.

```yaml
# Zéro IPC autorisé — accès HTTP uniquement
allowed_callers: []
```

La vérification est active quand `enforce_ipc: true` dans `integration.yaml` (défaut).

Voir [Multi-Tenancy](tenancy.md#autorisation-ipc) pour le fonctionnement complet.

---

## Rate limiting (`resources.rate_limit`)

```yaml
resources:
  rate_limit:
    calls: 500
    period_seconds: 60
```

Si non déclaré, la valeur `security.rate_limit_default` de `integration.yaml` s'applique (défaut : 200 appels / 60 s).

---

## Variables d'environnement (`env`)

```yaml
env:
  DATABASE_URL: "${DATABASE_URL}"   # variable OS requise
  STATIC: "valeur-fixe"
```

Accessibles dans le plugin :

```python
url = self.manifest.env["DATABASE_URL"]
```

---

## Configuration personnalisée (`extra`)

Tout champ non reconnu par xcore est stocké dans `manifest.extra` :

```yaml
# plugin.yaml
webhook_url: "https://hooks.example.com/xyz"
max_retries: 5
```

```python
url = self.manifest.extra["webhook_url"]
retries = self.manifest.extra["max_retries"]
```

---

## Exemples

### Plugin Trusted minimal

```yaml
name: billing
version: "1.0.0"
execution_mode: trusted
entry_point: src/main.py
allowed_callers:
  - dashboard
```

### Plugin Sandboxed

```yaml
name: pdf_renderer
version: "0.3.0"
execution_mode: sandboxed
entry_point: src/main.py
allowed_imports:
  - json
  - base64
  - re
resources:
  timeout_seconds: 5
  rate_limit:
    calls: 50
    period_seconds: 60
```

### Plugin complet

```yaml
name: inventory
version: "2.1.0"
author: "Backend Team"
description: "Gestion du stock produits"
execution_mode: trusted
entry_point: src/main.py

requires:
  - name: billing
    version: ">=1.0"
  - notifications

allowed_callers:
  - billing
  - dashboard

permissions:
  - action: read
    resource: "db:products"
  - action: write
    resource: "db:stock"

env:
  WAREHOUSE_API: "${WAREHOUSE_URL}"

resources:
  timeout_seconds: 15
  max_memory_mb: 256
  rate_limit:
    calls: 500
    period_seconds: 60

runtime:
  health_check:
    enabled: true
    interval_seconds: 60
  retry:
    max_attempts: 3
    backoff_seconds: 0.5

low_stock_threshold: 10
```

---

## Structure du dossier

```
plugins/my_plugin/
├── plugin.yaml      ← manifeste (ce fichier)
├── plugin.sig       ← signature HMAC (obligatoire si execution_mode: trusted)
└── src/
    ├── __init__.py
    └── main.py
```

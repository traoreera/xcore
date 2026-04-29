# Sécurité

XCore implémente une sécurité en profondeur (defense in depth) à plusieurs couches.

---

## 1. Moteur de Permissions

Chaque plugin déclare ses accès dans `plugin.yaml`. Le `PermissionEngine` évalue les requêtes inter-plugins à chaque appel.

### Déclaration des permissions

```yaml
# plugin.yaml
permissions:
  # Autoriser la lecture/écriture sur toutes les tables users
  - resource: "db.users.*"
    actions: ["read", "write"]
    effect: allow

  # Interdire l'accès aux données admin (priorité sur les règles suivantes)
  - resource: "db.admin.*"
    actions: ["*"]
    effect: deny

  # Cache en lecture/écriture
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

  # Autoriser uniquement l'écriture sur le filesystem temporaire
  - resource: "fs.tmp.*"
    actions: ["write"]
    effect: allow
```

### Règles d'évaluation

- Les règles sont évaluées **dans l'ordre** — première correspondance gagne.
- Aucune règle correspondante → **deny** par défaut (fail-closed).
- Les patterns `resource` supportent les globs (`*`, `?`, `[abc]`).
- Le champ `actions` accepte `["*"]` pour toutes les actions.

### Performances

Le moteur utilise un **cache LRU** par triplet `(plugin, resource, action)`. Latence mesurée : **113 µs** (avec cache) vs 152 µs (sans cache) pour 6 vérifications. Voir [Benchmarks](../reference/benchmarks.md).

---

## 2. Signature des plugins Trusted

En production, activer `strict_trusted: true` dans `xcore.yaml` force la vérification de la signature HMAC-SHA256 avant le chargement de tout plugin `trusted`.

```yaml
plugins:
  strict_trusted: true
  secret_key: "${PLUGIN_SECRET_KEY}"   # clé HMAC partagée
```

```bash
# Signer un plugin avant déploiement
poetry run xcore plugin sign plugins/mon_plugin --key "ma_clé"

# Cela génère plugins/mon_plugin/plugin.sig
# Vérifier
poetry run xcore plugin verify plugins/mon_plugin --key "ma_clé"
```

Un plugin `trusted` sans `plugin.sig` valide sera **refusé au chargement** si `strict_trusted: true`.

---

## 3. Sandbox multi-couches (plugins Sandboxed)

Les plugins `sandboxed` s'exécutent dans un **processus OS séparé** avec trois niveaux de protection :

### Couche 1 — Analyse statique AST

Avant toute exécution, l'`ASTScanner` parse l'arbre syntaxique du plugin et bloque :

```python
# BLOQUÉ par le scanner AST
import os                 # ❌ module interdit
import subprocess         # ❌ module interdit
eval("code")              # ❌ builtin interdit
exec("code")              # ❌ builtin interdit
obj.__class__             # ❌ attribut dangereux
obj.__globals__           # ❌ sandbox escape
type.__subclasses__()     # ❌ sandbox escape
```

Les modules autorisés se déclarent dans `allowed_imports` du manifeste :

```yaml
allowed_imports:
  - httpx
  - pydantic
  - json
  - datetime
```

### Couche 2 — Isolation processus (JSON-RPC 2.0)

La communication kernel ↔ sandbox se fait exclusivement via **pipes stdin/stdout** en JSON. Aucun objet Python natif ne passe la frontière (pas de `pickle`).

```
Kernel                 Pipe (JSON)           Sandbox Worker
  │                        │                       │
  │── {"method":"call"} ──►│──────────────────────►│
  │                        │                       │── exécute handler
  │◄── {"result": ...} ───│◄──────────────────────│
```

### Couche 3 — Limites de ressources

```yaml
resources:
  timeout_seconds: 10      # Kill si dépasse
  max_memory_mb: 128       # Kill si RSS dépasse
  rate_limit:
    calls: 100
    period_seconds: 60     # 429 si quota dépassé
```

---

## 4. Authentification HTTP (AuthBackend)

XCore fournit un système d'authentification pluggable via l'`AuthBackend` protocol.

### Implémenter un backend

```python
from xcore.kernel.api.auth import AuthBackend, AuthPayload, register_auth_backend

class JWTBackend:
    async def extract_token(self, request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    async def decode_token(self, token: str) -> AuthPayload | None:
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
            return AuthPayload(
                sub=payload["sub"],
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
            )
        except jwt.InvalidTokenError:
            return None

    async def has_permission(self, payload: AuthPayload, permission: str) -> bool:
        return permission in (payload.get("permissions") or [])

# Dans on_load() du plugin auth
class Plugin(TrustedBase):
    async def on_load(self):
        register_auth_backend(JWTBackend())

    async def on_unload(self):
        from xcore.kernel.api.auth import unregister_auth_backend
        unregister_auth_backend()
```

### Protéger des routes FastAPI

```python
from xcore.kernel.api.auth import get_current_user
from fastapi import Depends

@router.get("/profile")
async def profile(user = Depends(get_current_user)):
    return {"sub": user["sub"], "roles": user.get("roles", [])}
```

### RBAC déclaratif sur les routes plugins

```python
from xcore.sdk.decorators import route

@route("/admin/users", method="GET", permissions=["admin"])
async def list_all_users(self):
    # Accessible uniquement si l'utilisateur a la permission "admin"
    ...
```

---

## 5. Validation des manifestes

Le `ManifestValidator` vérifie chaque manifeste au chargement :

- Champs requis (`name`, `version`)
- `execution_mode` valide (`trusted` | `sandboxed`)
- `framework_version` compatible avec la version installée
- `allowed_imports` contient uniquement des noms de modules (pas de symboles)
- `plugin.sig` présent si `strict_trusted: true`

```bash
# Valider manuellement avant déploiement
poetry run xcore plugin validate plugins/mon_plugin
```

---

## 6. Bonnes pratiques

- Utiliser `strict_trusted: true` en production et signer tous les plugins.
- Privilegier `sandboxed` pour les plugins tiers ou non audités.
- Appliquer le **principe du moindre privilège** : ne déclarer que les permissions réellement utilisées.
- Ne jamais mettre `secret_key` en clair dans `xcore.yaml` — utiliser `"${SECRET_KEY}"` et `.env`.
- Auditer régulièrement avec `poetry run bandit -r xcore/ plugins/`.

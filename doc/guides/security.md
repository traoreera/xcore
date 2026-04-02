# Sécurité et Isolation

Guide complet sur les mécanismes de sécurité, l'isolation des plugins et les meilleures pratiques.

## Architecture de Sécurité Multi-couches

XCore implémente une stratégie de défense en profondeur pour protéger le noyau et les données du système.

1. **Sandboxing au niveau processus** — Isolation matérielle et OS (sous-processus).
2. **Contrôle d'accès au Filesystem** — Restriction granulaire des lectures/écritures.
3. **Analyse Statique (AST)** — Vérification du code avant exécution.
4. **Moteur de Permissions (RBAC/ABAC)** — Contrôle des capacités inter-plugins.
5. **Signature de Code** — Garantie de l'intégrité et de l'origine (HMAC-SHA256).

## Mode Sandboxed vs Mode Trusted

### Mode Sandboxed (Recommandé)

**Usage** : Plugins tiers, code non audité, environnements multi-tenants.

- **Isolation** : Chaque plugin tourne dans son propre processus Python.
- **Mémoire** : Limite stricte via `RLIMIT_AS` (configurable par plugin).
- **Disque** : Accès restreint au dossier `data/` du plugin uniquement.
- **Code** : Scan AST obligatoire, interdiction des built-ins dangereux.
- **Communication** : Uniquement via IPC (JSON-RPC) sécurisé.

### Mode Trusted

**Usage** : Extensions internes, services critiques nécessitant une performance maximale.

- **Isolation** : S'exécute dans le processus principal (Main Process).
- **Accès** : Accès complet aux services partagés et à l'API système.
- **Signature** : Signature obligatoire si `strict_trusted` est activé.
- **Performance** : Latence minimale, pas de sérialisation IPC.

## Protection du Système de Fichiers (FilesystemGuard)

Le `FilesystemGuard` intercepte tous les accès aux fichiers via un monkey-patching exhaustif de la bibliothèque standard.

```yaml
# plugin.yaml
filesystem:
  allowed_paths: ["data/", "logs/"] # Seuls ces dossiers sont accessibles
  denied_paths: ["src/", "../"]    # Blocage explicite même si imbriqué
```

**Actions bloquées en sandbox :**
- Ouverture de fichiers hors zone autorisée.
- Suppression, renommage ou création de dossiers (`os.mkdir`, `os.unlink`, etc.).
- Modification de permissions (`os.chmod`).
- Listage de répertoires système.

## Analyse Statique (ASTScanner)

Avant de charger un plugin sandboxé, XCore analyse son arbre de syntaxe abstraite (AST).

### Éléments interdits :
- **Imports système** : `os`, `sys`, `subprocess`, `ctypes`, `socket`, etc.
- **Built-ins dangereux** : `eval()`, `exec()`, `compile()`, `globals()`, `__import__()`.
- **Introspection sensible** : Accès à `__class__`, `__globals__`, `__subclasses__`, `__mro__`.
- **Probing** : L'utilisation de `hasattr()`, `getattr()`, `setattr()` est bloquée pour empêcher la découverte d'attributs cachés.

## Signature de Plugins

Pour garantir qu'un plugin n'a pas été modifié malveillamment, XCore supporte la signature HMAC-SHA256.

### Signer un plugin
```bash
xcore plugin sign ./plugins/mon_plugin --key VOTRE_CLE_SECRETE
```

Cela génère un fichier `plugin.sig` contenant l'empreinte de tous les fichiers du plugin.

### Vérification automatique
Dans `xcore.yaml`, vous pouvez forcer la vérification :
```yaml
plugins:
  strict_trusted: true # Refuse de charger un plugin Trusted non signé
```

## Moteur de Permissions

Le `PermissionEngine` gère qui peut faire quoi. Chaque plugin déclare ses besoins dans son manifeste.

```yaml
# plugin.yaml
permissions:
  - resource: "cache.*"     # Accès à toutes les clés du cache
    actions: ["read", "write"]
    effect: allow
  - resource: "db.users"    # Accès restreint à la table users
    actions: ["read"]
    effect: allow
```

**Optimisation de performance** : Les vérifications de permissions utilisent une mémoïsation interne, réduisant l'impact sur le "hot-path" à moins de 20 microsecondes.

## Bonnes Pratiques de Développement

### 1. Validation des Entrées (Pydantic)
Ne faites jamais confiance aux données reçues via IPC ou HTTP. Utilisez les décorateurs du SDK :

```python
from xcore.sdk import validate_payload, TrustedBase
from pydantic import BaseModel

class UserInput(BaseModel):
    user_id: int
    email: str

class Plugin(TrustedBase):
    @validate_payload(UserInput)
    async def handle_create(self, validated: UserInput):
        # Ici data est déjà validé et typé
        pass
```

### 2. Éviter les Injections SQL
Utilisez toujours les paramètres de requête fournis par le service DB, ne concaténez jamais de chaînes.

```python
# ✅ CORRECT
with self.db.session() as session:
    session.execute("SELECT * FROM users WHERE id = :id", {"id": user_id})
```

### 3. Gestion des Secrets
Ne stockez jamais de clés API en dur dans le code. Utilisez le bloc `env` du manifeste ou des variables d'environnement système.

```yaml
# plugin.yaml
env:
  STRIPE_KEY: "${STRIPE_API_KEY}" # Sera résolu depuis l'environnement système
```

## Checklist de Sécurité Production

- [ ] `debug: false` dans la configuration globale.
- [ ] `execution_mode: sandboxed` pour tous les plugins tiers.
- [ ] `strict_trusted: true` activé.
- [ ] Clés secrètes (`secret_key`) générées aléatoirement (min 32 caractères).
- [ ] Limites de ressources (`max_memory_mb`) configurées pour chaque plugin sandboxé.
- [ ] Rate limiting global et par plugin activé.
- [ ] HTTPS activé sur le reverse proxy (Nginx/Traefik).

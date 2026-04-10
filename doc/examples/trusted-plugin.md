# Exemple : Plugin de Confiance (Trusted Plugin)

Le mode `trusted` est conçu pour les plugins internes qui ont un accès total au système et aux services partagés.

---

## 1. Caractéristiques du mode Trusted

- **Processus Partagé** : S'exécute dans le même processus que le Noyau (Kernel).
- **Accès Direct** : Peut manipuler les instances de services (`db`, `cache`, `scheduler`) directement.
- **Routage HTTP** : Peut exposer des routers FastAPI personnalisés.
- **Performance** : Pas d'overhead de communication IPC.
- **Signature Requise** : En production, les plugins Trusted doivent être signés pour être chargés (`strict_trusted: true`).

---

## 2. Le Manifeste (`plugin.yaml`)

```yaml
name: core_auth
version: 2.1.0
author: XCore Internal Team
description: Service d'authentification central du framework
execution_mode: trusted
entry_point: src/main.py

# Déclarer les services requis pour l'initialisation
requires:
  - database_service
  - cache_service

# Permissions RBAC
permissions:
  - resource: "db.users"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.auth_tokens"
    actions: ["write"]
    effect: allow
```

---

## 3. Le Code Source (`src/main.py`)

```python
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    action,
    ok,
    error,
    require_service
)
import bcrypt

class Plugin(AutoDispatchMixin, TrustedBase):
    """
    Plugin Trusted gérant l'authentification.
    """

    async def on_load(self) -> None:
        """Accès direct aux services."""
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.logger.info("Service d'authentification prêt.")

    @action("register")
    @require_service("db")
    async def register_user(self, payload: dict) -> dict:
        """
        Action Trusted pour enregistrer un nouvel utilisateur.
        Accès total aux API Python (ex: bcrypt).
        """
        username = payload.get("username")
        password = payload.get("password")

        if not username or not password:
            return error("Paramètres manquants")

        # Hashage du mot de passe (CPU intensif)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Insertion directe en DB
        async with self.db.session() as session:
            # Imaginons que nous utilisons une fonction helper ici
            # user_id = await create_db_user(session, username, hashed)
            pass

        return ok(username=username, status="registered")

    @action("validate_token")
    @require_service("cache")
    async def validate_token(self, payload: dict) -> dict:
        """
        Vérification rapide d'un token dans le cache partagé.
        """
        token = payload.get("token")
        if not token:
            return error("Token manquant")

        # Lecture directe du cache Redis partagé
        user_data = await self.cache.get(f"auth:token:{token}")

        if user_data:
            return ok(valid=True, user=user_data)

        return ok(valid=False)
```

---

## 4. Points Clés de l'Exemple

✅ **Accès Full-Stack** : Accès à toutes les bibliothèques Python (`bcrypt`, `psycopg2`, etc.).
✅ **Services Partagés** : Utilisation intensive du cache et de la base de données sans latence.
✅ **Hautes Performances** : Idéal pour les fonctions de sécurité, d'authentification ou de traitement d'image.
✅ **Sécurité de Chargement** : Ce plugin doit être déposé dans le dossier `./plugins` par l'administrateur système.

# Plugins vs Extensions/Services

xcore distingue deux types de composants : les **plugins** et les **extensions/services**. Comprendre cette différence est fondamental pour savoir où placer votre code.

---

## Plugins (`plugins/`)

Un plugin est un **module autonome et dynamique** qui étend l'API de votre application.

**Caractéristiques :**

- Chargé et déchargé **dynamiquement** à l'exécution
- Expose des **routes FastAPI** via un `APIRouter`
- Possède ses propres métadonnées (`PLUGIN_INFO`)
- Peut être activé/désactivé, rechargé ou mis à jour sans redémarrer le serveur
- Isolé des autres plugins (sandbox)
- Découvert automatiquement par le `PluginLoader`

**Quand créer un plugin ?**

Créez un plugin lorsque vous ajoutez une **fonctionnalité métier** indépendante et exposée via l'API : un service d'email, un module de facturation, un système de notifications, un webhook, etc.

```
plugins/
└── email_plugin/       ← fonctionnalité métier autonome
    ├── __init__.py
    ├── run.py          ← PLUGIN_INFO + Plugin class + router
    ├── router.py
    └── config.yaml
```

---

## Extensions / Services (`extensions/services/`)

Une extension ou un service est un **composant transversal** partagé entre plusieurs plugins.

**Caractéristiques :**

- Chargé **statiquement** au démarrage de l'application
- Ne déclare pas de `PLUGIN_INFO` ni de `Plugin` class
- Fournit des **utilitaires réutilisables** : connexion DB, cache, auth, sécurité
- Injecté dans les plugins via les mécanismes de dépendance FastAPI (`Depends`)
- Géré directement par le core de xcore, pas par le `PluginLoader`

**Quand créer une extension/service ?**

Créez un service lorsque vous avez une fonctionnalité **transversale** que plusieurs plugins doivent partager : une connexion à la base de données, un client Redis, un service d'authentification JWT, etc.

```
extensions/services/
├── auth/           ← JWT, sessions (partagé par tous les plugins)
├── cache/          ← client Redis (partagé)
├── database/       ← SQLAlchemy session (partagé)
└── security/       ← hachage, tokens (partagé)
```

---

## Comparaison rapide

| Critère | Plugin | Extension/Service |
|---------|--------|-------------------|
| Emplacement | `plugins/` | `extensions/services/` |
| Chargement | Dynamique (runtime) | Statique (startup) |
| Expose des routes API | ✅ Oui | ❌ Non |
| Hot reload | ✅ Oui | ❌ Non |
| Isolation sandbox | ✅ Oui | ❌ Non |
| Partagé entre plugins | ❌ Non | ✅ Oui |
| `PLUGIN_INFO` requis | ✅ Oui | ❌ Non |
| Exemple | email, facturation | auth, cache, DB |

---

## Comment un plugin utilise un service

Un plugin peut consommer un service via l'injection de dépendances FastAPI :

```python
# dans plugins/mon_plugin/run.py
from fastapi import Depends
from extensions.services.database import get_db
from extensions.services.auth import get_current_user
from sqlalchemy.orm import Session

@router.get("/mes-donnees")
def get_data(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    # accès à la DB et à l'utilisateur connecté
    return {"user": user.email}
```

Le plugin reste autonome et portable — il déclare ce dont il a besoin, et xcore s'occupe de l'injection.

# Exemples de Plugins XCore

Ce répertoire contient des exemples complets de plugins pour le framework XCore, illustrant les différents modes d'exécution et les patterns avancés.

## Table des Matières

| Exemple | Mode | Complexité | Description |
|---------|------|------------|-------------|
| [basic-plugin](./basic-plugin.md) | Trusted | Débutant | Plugin calculatrice simple avec HTTP et IPC |
| [trusted-plugin](./trusted-plugin.md) | **Trusted** | Avancé | Gestionnaire de tâches avec router.py séparé et .env |
| [sandboxed-plugin](./sandboxed-plugin.md) | **Sandboxed** | Avancé | Convertisseur de documents sécurisé |

---

## Choix du Mode d'Exécution

```
┌─────────────────────────────────────────────────────────────────┐
│                    Quel mode choisir ?                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐          ┌──────────────────┐               │
│  │   Trusted    │          │    Sandboxed     │               │
│  │              │          │                  │               │
│  │ • Accès DB   │          │ • Isolation max  │               │
│  │ • Services   │          │ • Ressources     │               │
│  │ • Filesystem │          │   limitées       │               │
│  │   étendu     │          │ • Liste blanche  │               │
│  │              │          │   imports        │               │
│  └──────┬───────┘          └────────┬─────────┘               │
│         │                           │                          │
│         ▼                           ▼                          │
│  ┌─────────────────┐      ┌────────────────────┐              │
│  │ Gestion users   │      │ Traitement fichiers│              │
│  │ Notifications   │      │ Conversion docs    │              │
│  │ Cache complexe  │      │ Exécution code     │              │
│  │ Analytics       │      │ Compression        │              │
│  └─────────────────┘      └────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Structure Type d'un Plugin

### Mode Trusted (avec .env)

```
plugins/mon_plugin/
├── plugin.yaml          # Manifest + config structurelle
├── .env                 # Variables sensibles (non commité)
├── src/
│   ├── __init__.py
│   ├── main.py         # Point d'entrée, cycle de vie
│   ├── router.py       # Routes HTTP FastAPI
│   ├── services.py     # Logique métier
│   └── models.py       # Dataclasses/Pydantic
└── data/               # Persistence locale
    └── ...
```

### Mode Sandboxed

```
plugins/mon_plugin/
├── plugin.yaml          # Manifest avec restrictions
├── src/
│   ├── __init__.py
│   ├── main.py         # Plugin Sandboxed
│   ├── router.py       # Routes HTTP
│   └── converter.py    # Logique isolée
└── data/temp/          # Zone de travail temporaire
```

---

## Pattern Router.py Séparé

Les deux exemples avancés utilisent un pattern de séparation des routes HTTP :

### Avantages

1. **Séparation des responsabilités** : Le routage HTTP est isolé de la logique métier
2. **Testabilité** : Les routes peuvent être testées indépendamment
3. **Lisibilité** : Le fichier `main.py` reste concentré sur le cycle de vie et les actions IPC
4. **Réutilisation** : La logique métier peut être utilisée sans HTTP

### Implémentation

```python
# src/router.py
def create_router(plugin_instance) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["mon-plugin"])

    @router.get("/items")
    async def list_items():
        return await plugin_instance.service.get_items()

    return router

# src/main.py
class Plugin(TrustedBase):
    def get_router(self) -> APIRouter | None:
        from .router import create_router
        return create_router(self)
```

---

## Pattern Configuration via .env (Trusted uniquement)

### Structure

```yaml
# plugin.yaml
env:
  DB_POOL_SIZE: "10"
  API_KEY: ""

envconfiguration:
  inject: true        # Injecte les variables dans ctx.env
  required: true    # Échoue si .env manquant
```

```bash
# .env (non commité)
DB_POOL_SIZE=20
API_KEY=sk_live_xxx
SECRET_KEY=super_secret
```

### Utilisation

```python
async def on_load(self):
    self.config = {
        "pool_size": int(self.ctx.env.get("DB_POOL_SIZE", "10")),
        "api_key": self.ctx.env.get("API_KEY"),
    }
```

---

## Points Clés par Mode

### Trusted

- ✅ Accès complet aux services (DB, Cache, Email, Scheduler)
- ✅ Filesystem configurable
- ✅ Imports Python illimités
- ✅ Configuration via `.env`
- ⚠️ Attention aux injections SQL et XSS
- ⚠️ Valider toutes les entrées utilisateur

### Sandboxed

- 🔒 Isolation complète du système
- 🔒 Ressources limitées (mémoire, CPU, disque)
- 🔒 Liste blanche d'imports
- 🔒 Timeout sur les opérations
- ✅ Idéal pour le traitement de fichiers
- ❌ Pas d'accès DB direct

---

## Commandes Rapides

### Créer un nouveau plugin

```bash
# Structure de base
mkdir -p plugins/mon_plugin/src plugins/mon_plugin/data

# Fichiers nécessaires
touch plugins/mon_plugin/plugin.yaml
touch plugins/mon_plugin/src/__init__.py
touch plugins/mon_plugin/src/main.py

# Si Trusted avec .env
touch plugins/mon_plugin/.env
echo ".env" >> plugins/mon_plugin/.gitignore
```

### Tester un plugin

```bash
# Démarrer XCore
python -m xcore.server

# Tester HTTP
curl http://localhost:8082/plugins/mon_plugin/health

# Tester IPC
curl -X POST http://localhost:8082/app/mon_plugin/action \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

---

## Ressources Complémentaires

- [Documentation Principale](../README.md)
- [Référence API du SDK](../../xcore/sdk/)
- [Guide de Sécurité](../security.md)
- [Dépannage](../troubleshooting.md)

---

## Contributions

Ces exemples sont maintenus par l'équipe XCore. Pour suggérer des améliorations ou signaler des problèmes :

1. Forker le dépôt
2. Créer une branche (`git checkout -b improve-examples`)
3. Commiter vos changements
4. Ouvrir une Pull Request

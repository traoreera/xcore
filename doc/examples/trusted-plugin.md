# Exemple de Plugin de Confiance (Trusted)

Cet exemple présente un plugin de gestion de tâches avancé fonctionnant en mode `trusted`. Il illustre l'accès complet aux services Core, l'utilisation de routes HTTP FastAPI complexes et la configuration sécurisée via `.env`.

## Cas d'usage : Task Manager

Ce plugin est en mode `trusted` car il nécessite un accès haute performance à la base de données SQL et au bus d'événements global pour coordonner des tâches système.

## Structure du Plugin

```text
plugins/task_manager/
├── plugin.yaml
├── .env                  # Fichier de secrets (non versionné)
└── src/
    ├── main.py          # Orchestrateur
    ├── models.py        # Modèles Pydantic/ORM
    └── router.py        # Endpoints FastAPI
```

## `plugin.yaml`

```yaml
name: task_manager
version: 2.0.0
author: XCore Team
description: Orchestrateur de tâches système avec accès privilégié

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

# Activation de l'injection .env sécurisée
envconfiguration:
  inject: true

permissions:
  - resource: "db.*"
    actions: ["*"]
    effect: allow
  - resource: "events.*"
    actions: ["emit", "subscribe"]
    effect: allow
```

## `src/main.py`

Utilisation de `TrustedBase` et de l'objet `self.ctx` complet.

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok, error
from .router import create_task_router

class Plugin(AutoDispatchMixin, TrustedBase):
    """Plugin privilégié avec accès total aux ressources du noyau."""

    async def on_load(self):
        # 1. Récupération d'un secret depuis le .env injecté via self.ctx.env
        self.api_key = self.ctx.env.get("TASKS_API_KEY")

        # 2. Accès direct aux services Core
        self.db = self.get_service("db")
        self.events = self.ctx.events

        print(f"Task Manager v{self.ctx.version} opérationnel")

    def get_router(self):
        """Délégation du routage HTTP à un module dédié."""
        return create_task_router(self)

    @action("cleanup")
    async def cleanup_tasks(self, payload: dict):
        """Action IPC performante manipulant directement la DB."""
        with self.db.session() as session:
            try:
                # Utilisation du mode Trusted pour des requêtes complexes
                res = session.execute("DELETE FROM tasks WHERE status = 'archived'")
                session.commit()

                # Émission d'un événement global
                await self.events.emit("tasks.cleaned", {"count": res.rowcount})
                return ok(deleted=res.rowcount)
            except Exception as e:
                return error(str(e))
```

## Points clés démontrés

1.  **Injection .env** : Utilisation de `envconfiguration.inject: true` pour charger des secrets (clés API, credentials DB) de manière sécurisée sans les inclure dans le code source.
2.  **Performance In-Process** : Exécution dans le processus principal, permettant des transactions SQL directes sans passer par une sérialisation IPC coûteuse.
3.  **Délégation de Router** : Organisation modulaire du code en renvoyant un `APIRouter` complexe depuis `get_router()`.
4.  **Contexte Global** : Accès au bus d'événements (`self.ctx.events`) pour interagir avec d'autres composants du framework.

# base.py (BaseService)

Le fichier `xcore/integration/plugins/base.py` définit le contrat minimal d’une extension de service.

## Rôle

`BaseService` fournit:

- `self.name` : nom déclaré dans `integration.yaml`
- `self.config` : bloc `config` de l’extension
- `self.env` : variables d’environnement résolues
- `self.registry` : accès aux autres services

## API

- `async setup()` : initialisation du service
- `async teardown()` : arrêt/cleanup
- `get_service(name)` : résolution d’un autre service
- `is_ready` : état de disponibilité

## Exemple

```python
from xcore.integration.plugins.base import BaseService

class EmailService(BaseService):
    async def setup(self):
        token = self.env.get("API_TOKEN")
        self.client = object()
        self._mark_ready()

    async def teardown(self):
        self.client = None
```

## Contribution

- Les services concrets doivent rester idempotents (`setup`/`teardown`).
- Toujours appeler `_mark_ready()` après une initialisation réussie.

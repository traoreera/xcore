# Utiliser un plugin

Ce tutoriel explique comment interagir avec les plugins existants : via l'API HTTP, via le Manager, et comment un plugin peut en utiliser un autre.

---

## Consommer un plugin via HTTP

Tous les plugins sont accessibles via leur préfixe d'API défini dans `PLUGIN_INFO["Api_prefix"]`.

```bash
# Health check d'un plugin
curl http://localhost:8000/app/nom_plugin/

# Appel d'une route spécifique
curl -X POST http://localhost:8000/app/email/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["user@example.com"],
    "subject": "Test",
    "body": "Message de test"
  }'
```

La documentation interactive de toutes les routes est disponible sur `http://localhost:8000/docs`.

---

## Gérer les plugins via le Manager

Le Manager expose des endpoints d'administration pour contrôler les plugins sans redémarrer le serveur.

### Lister les plugins actifs

```bash
curl http://localhost:8000/admin/plugins
```

Réponse :
```json
[
  {
    "name": "email_plugin",
    "version": "1.0.0",
    "status": "active",
    "routes": ["/app/email/", "/app/email/send", "/app/email/send/template"]
  },
  {
    "name": "todo_plugin",
    "version": "1.0.0",
    "status": "active",
    "routes": ["/app/todo/"]
  }
]
```

### Recharger un plugin

```bash
curl -X POST http://localhost:8000/admin/plugins/email_plugin/reload
```

### Désactiver un plugin

```bash
curl -X POST http://localhost:8000/admin/plugins/todo_plugin/disable
```

---

## Utiliser un plugin depuis un autre plugin

Les plugins ne doivent **pas** s'importer directement les uns les autres (couplage fort, fragile au hot reload). Privilégiez deux approches :

### Approche 1 — Via les services partagés

Si deux plugins ont besoin de la même logique, externalisez-la dans `extensions/services/`.

```python
# extensions/services/notification/service.py
def envoyer_notification(user_id: int, message: str): ...

# Dans plugin A
from extensions.services.notification import envoyer_notification

# Dans plugin B
from extensions.services.notification import envoyer_notification
```

### Approche 2 — Via des appels HTTP internes

Pour rester totalement découplés, un plugin peut appeler les routes d'un autre plugin via HTTP avec `httpx` :

```python
import httpx
from fastapi import APIRouter, Request, BackgroundTasks

router = APIRouter(prefix="/commande", tags=["commande"])

@router.post("/valider/{commande_id}")
async def valider_commande(commande_id: int, background_tasks: BackgroundTasks):
    # Logique de validation...
    
    # Envoyer un email de confirmation via le plugin email
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8000/app/email/send",
            json={
                "to": ["client@example.com"],
                "subject": f"Commande #{commande_id} confirmée",
                "body": "Votre commande a été validée."
            }
        )
    
    return {"status": "validée", "commande_id": commande_id}
```

---

## Authentification sur les routes protégées

Si un plugin utilise l'authentification JWT du core, incluez le token dans vos requêtes :

```bash
# 1. Obtenir un token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "motdepasse"}'

# 2. Utiliser le token
curl http://localhost:8000/app/mon_plugin/donnees-protegees \
  -H "Authorization: Bearer <votre_token>"
```

Côté plugin, pour protéger une route :

```python
from extensions.services.auth import get_current_user
from fastapi import Depends

@router.get("/donnees-protegees")
def donnees_protegees(user = Depends(get_current_user)):
    return {"user": user.email, "data": "..."}
```

---

## Surveiller l'utilisation d'un plugin

Consultez les logs et statistiques d'un plugin via le Manager :

```bash
# Logs du plugin
curl http://localhost:8000/admin/plugins/email_plugin/logs

# Statistiques (requêtes, erreurs, temps moyen)
curl http://localhost:8000/admin/plugins/email_plugin/stats
```

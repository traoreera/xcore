# Référence de l'API HTTP XCore

XCore expose deux types d'APIs HTTP via le framework FastAPI :
1. **API Système** : Pour la gestion interne et l'IPC (Inter-Process Communication).
2. **API Plugins** : Routes personnalisées exposées par les plugins Trusted.

---

## 1. API Système (`/plugin/ipc`)

Cette API est sécurisée par une clé API transmise via l'entête `X-Plugin-Key`.

### Point d'entrée IPC : `POST /plugin/ipc/{plugin_name}/{action}`
Permet d'appeler une action spécifique d'un plugin chargé.

**Payload :**
```json
{
  "payload": {
    "key": "value"
  }
}
```

**Réponse :**
```json
{
  "status": "ok",
  "plugin": "mon_plugin",
  "action": "dire_bonjour",
  "result": { ... }
}
```

### Gestion des Plugins
| Méthode | Route | Description |
|---------|-------|-------------|
| **GET** | `/plugin/ipc/status` | Liste l'état de tous les plugins (loaded, idle, error). |
| **POST** | `/plugin/ipc/{name}/load` | Charge un plugin dynamiquement. |
| **POST** | `/plugin/ipc/{name}/reload` | Recharge un plugin (Hot-reload). |
| **DELETE** | `/plugin/ipc/{name}/unload` | Décharge un plugin de la mémoire. |

### Santé et Métriques
| Méthode | Route | Description |
|---------|-------|-------------|
| **GET** | `/plugin/ipc/health` | Diagnostic global de santé (DB, Cache, Plugins). |
| **GET** | `/plugin/ipc/metrics` | Snapshot JSON des métriques du système. |

---

## 2. API des Plugins (`/plugin/{plugin_name}`)

Les plugins Trusted peuvent exposer leurs propres routes HTTP REST. Ces routes sont automatiquement montées sous un préfixe structuré.

**Exemple :**
Si un plugin nommé `shop` définit une route `/items`, elle sera accessible sur :
`http://localhost:8082/plugin/shop/items`

- **Routage dynamique** : XCore utilise le `RouterRegistry` pour collecter et monter les routers FastAPI fournis par les plugins via la méthode `get_router()`.
- **RBAC intégré** : Si des permissions sont définies via le décorateur `@route`, XCore vérifie automatiquement les droits via l'entête `Authorization` avant d'appeler le handler du plugin.

---

## 3. Sécurité de l'API

### Entêtes Requis
- **IPC** : `X-Plugin-Key: <votre_secret_key>`
- **REST Plugins** : `Authorization: Bearer <votre_jwt>` (selon la configuration du plugin).

### Codes de Réponse Standard
- `200 OK` : Succès.
- `401 Unauthorized` : Clé API incorrecte ou manquante.
- `404 Not Found` : Plugin ou action non trouvé.
- `500 Internal Server Error` : Erreur interne lors de l'exécution de l'action par le plugin.

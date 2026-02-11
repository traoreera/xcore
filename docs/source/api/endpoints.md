# Référence API

Documentation complète de l'API REST xcore.

## Base URL

```
https://api.example.com
```

## Authentification

L'API utilise JWT (JSON Web Tokens) pour l'authentification.

### Obtenir un Token

```text
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=email@example.com&password=password
```

**Réponse 200:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Utiliser le Token

```text
GET /auth/me
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## Codes de Statut HTTP

| Code | Description |
|------|-------------|
| 200 | OK - Requête réussie |
| 201 | Created - Ressource créée |
| 204 | No Content - Pas de contenu à retourner |
| 400 | Bad Request - Requête invalide |
| 401 | Unauthorized - Authentification requise |
| 403 | Forbidden - Permissions insuffisantes |
| 404 | Not Found - Ressource non trouvée |
| 409 | Conflict - Conflit de données |
| 422 | Validation Error - Erreur de validation |
| 500 | Internal Server Error - Erreur serveur |

## Endpoints d'Authentification

### POST /auth/register

Créer un nouvel utilisateur.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Response 201:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### POST /auth/login

Authentifier un utilisateur.

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### GET /auth/me

Récupérer l'utilisateur connecté.

**Headers:**
```
Authorization: Bearer {token}
```

**Response 200:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "roles": ["user"],
  "permissions": ["read:users"]
}
```

### POST /auth/refresh

Rafraîchir le token d'accès.

**Headers:**
```
Authorization: Bearer {token}
```

**Response 200:**
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Endpoints d'Administration

### Rôles

#### GET /admin/roles

Lister tous les rôles.

**Query Parameters:**
- `skip` (int): Décalage pagination (défaut: 0)
- `limit` (int): Limite résultats (défaut: 20, max: 100)

**Response 200:**
```json
{
  "total": 3,
  "items": [
    {
      "id": 1,
      "name": "admin",
      "description": "Administrateur système",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /admin/roles

Créer un nouveau rôle.

**Request Body:**
```json
{
  "name": "manager",
  "description": "Gestionnaire d'équipe"
}
```

**Response 201:**
```json
{
  "id": 2,
  "name": "manager",
  "description": "Gestionnaire d'équipe",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET /admin/roles/{role_id}

Récupérer un rôle spécifique.

**Response 200:**
```json
{
  "id": 1,
  "name": "admin",
  "description": "Administrateur système",
  "permissions": [
    {
      "id": 1,
      "name": "users:read",
      "description": "Lire les utilisateurs"
    }
  ],
  "users_count": 5
}
```

#### PUT /admin/roles/{role_id}

Mettre à jour un rôle.

**Request Body:**
```json
{
  "name": "admin",
  "description": "Super administrateur"
}
```

#### DELETE /admin/roles/{role_id}

Supprimer un rôle.

**Response 204:** No Content

### Permissions

#### GET /admin/permissions

Lister toutes les permissions.

**Response 200:**
```json
{
  "total": 10,
  "items": [
    {
      "id": 1,
      "name": "users:read",
      "description": "Lire les utilisateurs",
      "resource": "users",
      "action": "read"
    }
  ]
}
```

#### POST /admin/permissions

Créer une nouvelle permission.

**Request Body:**
```json
{
  "name": "reports:generate",
  "description": "Générer des rapports",
  "resource": "reports",
  "action": "generate"
}
```

### Gestion Utilisateurs

#### GET /admin/users

Lister tous les utilisateurs (admin seulement).

**Query Parameters:**
- `skip` (int): Décalage pagination
- `limit` (int): Limite résultats
- `search` (string): Recherche par email/nom
- `is_active` (boolean): Filtrer par statut

**Response 200:**
```json
{
  "total": 50,
  "items": [
    {
      "id": 1,
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_active": true,
      "roles": ["user"],
      "last_login": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /admin/users/{user_id}/roles/{role_id}

Assigner un rôle à un utilisateur.

**Response 200:**
```json
{
  "message": "Rôle assigné avec succès"
}
```

#### DELETE /admin/users/{user_id}/roles/{role_id}

Retirer un rôle d'un utilisateur.

**Response 204:** No Content

#### POST /admin/users/{user_id}/activate

Activer un utilisateur.

**Response 200:**
```json
{
  "id": 1,
  "is_active": true
}
```

#### POST /admin/users/{user_id}/deactivate

Désactiver un utilisateur.

**Response 200:**
```json
{
  "id": 1,
  "is_active": false
}
```

## Endpoints du Manager de Plugins

### Plugins

#### GET /system/plugins

Lister tous les plugins.

**Query Parameters:**
- `active_only` (boolean): Ne retourner que les plugins actifs

**Response 200:**
```json
{
  "total": 5,
  "items": [
    {
      "id": "erp_core",
      "name": "ERP Core",
      "version": "1.0.0",
      "author": "XCore Team",
      "active": true,
      "api_prefix": "/erp",
      "tags": ["erp", "core"],
      "loaded_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /system/plugins

Installer un nouveau plugin.

**Request Body:**
```json
{
  "name": "mon_plugin",
  "source": "https://github.com/user/plugin.git",
  "version": "1.0.0"
}
```

**Response 201:**
```json
{
  "id": "mon_plugin",
  "status": "installed",
  "message": "Plugin installé avec succès"
}
```

#### GET /system/plugins/{plugin_id}

Récupérer les détails d'un plugin.

**Response 200:**
```json
{
  "id": "erp_crm",
  "name": "ERP CRM",
  "version": "1.0.0",
  "author": "XCore Team",
  "description": "Module CRM complet",
  "active": true,
  "api_prefix": "/erp/crm",
  "tags": ["crm", "customers"],
  "routes": [
    "/erp/crm/customers",
    "/erp/crm/opportunities",
    "/erp/crm/dashboard"
  ],
  "dependencies": ["erp_core"],
  "loaded_at": "2024-01-15T10:00:00Z",
  "last_reload": "2024-01-15T12:00:00Z"
}
```

#### POST /system/plugins/{plugin_id}/reload

Recharger un plugin.

**Response 200:**
```json
{
  "id": "erp_crm",
  "status": "reloaded",
  "message": "Plugin rechargé avec succès"
}
```

#### POST /system/plugins/{plugin_id}/enable

Activer un plugin.

**Response 200:**
```json
{
  "id": "erp_crm",
  "active": true
}
```

#### POST /system/plugins/{plugin_id}/disable

Désactiver un plugin.

**Response 200:**
```json
{
  "id": "erp_crm",
  "active": false
}
```

#### DELETE /system/plugins/{plugin_id}

Désinstaller un plugin.

**Response 204:** No Content

### Tâches en Arrière-Plan

#### GET /system/tasks

Lister toutes les tâches planifiées.

**Response 200:**
```json
{
  "total": 3,
  "items": [
    {
      "id": "cleanup_logs",
      "name": "Nettoyage des logs",
      "type": "scheduled",
      "status": "running",
      "schedule": "0 0 * * *",
      "last_run": "2024-01-14T00:00:00Z",
      "next_run": "2024-01-15T00:00:00Z",
      "success_count": 14,
      "failure_count": 0
    }
  ]
}
```

#### POST /system/tasks

Créer une nouvelle tâche.

**Request Body:**
```json
{
  "id": "ma_tache",
  "name": "Ma Tâche",
  "type": "interval",
  "interval": {
    "hours": 1
  },
  "enabled": true
}
```

#### POST /system/tasks/{task_id}/run

Exécuter une tâche immédiatement.

**Response 200:**
```json
{
  "id": "ma_tache",
  "status": "running",
  "started_at": "2024-01-15T10:30:00Z"
}
```

#### POST /system/tasks/{task_id}/pause

Mettre une tâche en pause.

**Response 200:**
```json
{
  "id": "ma_tache",
  "status": "paused"
}
```

#### POST /system/tasks/{task_id}/resume

Reprendre une tâche.

**Response 200:**
```json
{
  "id": "ma_tache",
  "status": "scheduled"
}
```

## Endpoints de Monitoring

### Health Check

#### GET /health

Vérifier l'état du système.

**Response 200:**
```json
{
  "status": "healthy",
  "checks": {
    "database": true,
    "redis": true,
    "disk": true
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "uptime": 3600
}
```

### Métriques

#### GET /metrics

Métriques Prometheus (si activé).

**Response 200:** (text/plain)
```
# HELP xcore_requests_total Total requests
# TYPE xcore_requests_total counter
xcore_requests_total{method="GET",endpoint="/health"} 1234

# HELP xcore_request_duration_seconds Request duration
# TYPE xcore_request_duration_seconds histogram
xcore_request_duration_seconds_bucket{le="0.1"} 100
```

## Endpoints Frontend

### Templates

#### GET /

Page d'accueil.

**Response 200:** HTML

#### GET /core-docs

Documentation API (ReDoc).

**Response 200:** HTML

### Fichiers Statiques

#### GET /static/{path}

Servir des fichiers statiques.

## Filtrage et Pagination

### Syntaxe de Filtrage

```text
GET /admin/users?search=john&is_active=true&skip=0&limit=20
```

### Format de Réponse Paginée

Tous les endpoints de liste retournent :

```text
{
  "total": 100,
  "skip": 0,
  "limit": 20,
  "items": [...],
  "has_more": true
}
```

### Tri

```text
GET /admin/users?sort_by=created_at&sort_order=desc
```

## Gestion des Erreurs

### Format d'Erreur Standard

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ],
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_123456789"
  }
}
```

### Codes d'Erreur Communs

| Code | Description | Solution |
|------|-------------|----------|
| `AUTHENTICATION_ERROR` | Token invalide ou expiré | Renouvelez le token |
| `AUTHORIZATION_ERROR` | Permissions insuffisantes | Vérifiez les rôles |
| `VALIDATION_ERROR` | Données invalides | Corrigez les champs |
| `NOT_FOUND` | Ressource inexistante | Vérifiez l'ID |
| `CONFLICT` | Conflit de données | Vérifiez les unicités |
| `RATE_LIMIT` | Trop de requêtes | Attendez avant de réessayer |

## Rate Limiting

Les limites sont appliquées par IP et par token :

- **Authentifié**: 1000 requêtes/heure
- **Non authentifié**: 100 requêtes/heure
- **Admin**: 10000 requêtes/heure

**Headers de Réponse:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642276800
```

## WebSockets (si disponible)

### Connexion

```javascript
const ws = new WebSocket('wss://api.example.com/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'Bearer eyJ0eXAi...'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

### Événements

- `plugin.loaded` - Plugin chargé
- `plugin.reloaded` - Plugin rechargé
- `task.completed` - Tâche terminée
- `user.login` - Utilisateur connecté

## SDK et Clients

### Exemple cURL

```bash
# Authentification
TOKEN=$(curl -s -X POST https://api.example.com/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=secret" \
  | jq -r '.access_token')

# Utiliser le token
curl https://api.example.com/admin/users \
  -H "Authorization: Bearer $TOKEN"
```

### Exemple Python

```python
import requests

# Authentification
response = requests.post(
    "https://api.example.com/auth/login",
    data={"username": "admin@example.com", "password": "secret"}
)
token = response.json()["access_token"]

# Requête API
headers = {"Authorization": f"Bearer {token}"}
users = requests.get(
    "https://api.example.com/admin/users",
    headers=headers
).json()
```

### Exemple JavaScript

```javascript
// Authentification
const login = async () => {
  const response = await fetch('https://api.example.com/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=admin@example.com&password=secret'
  });
  const data = await response.json();
  return data.access_token;
};

// Utiliser le token
const getUsers = async (token) => {
  const response = await fetch('https://api.example.com/admin/users', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};
```

## Changements et Versions

### Versions de l'API

L'API suit le versioning sémantique. La version actuelle est **v1**.

### Changements Breaking

Les changements breaking sont annoncés 30 jours à l'avance via :
- Changelog
- Email aux développeurs
- Header `X-API-Deprecated` dans les réponses

### Changelog

Voir le changelog du projet dans le dépôt source pour l'historique des modifications.

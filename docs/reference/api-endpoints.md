# Référence des endpoints API

Cette page liste tous les endpoints exposés par le core de xcore (hors plugins).

---

## Authentification — `/auth`

| Méthode | Route | Description | Auth requise |
|---------|-------|-------------|--------------|
| `POST` | `/auth/login` | Connexion, retourne un token JWT | ❌ |
| `POST` | `/auth/logout` | Invalidation du token | ✅ |
| `POST` | `/auth/refresh` | Renouveler un token expiré | ✅ |
| `GET` | `/auth/me` | Informations de l'utilisateur connecté | ✅ |

### `POST /auth/login`

```json
// Corps de la requête
{
  "email": "user@example.com",
  "password": "motdepasse"
}

// Réponse 200
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Utilisateurs — `/user`

| Méthode | Route | Description | Auth requise |
|---------|-------|-------------|--------------|
| `POST` | `/user/register` | Créer un compte | ❌ |
| `GET` | `/user/profile` | Consulter son profil | ✅ |
| `PUT` | `/user/profile` | Mettre à jour son profil | ✅ |
| `PUT` | `/user/password` | Changer son mot de passe | ✅ |

### `POST /user/register`

```json
// Corps
{
  "email": "user@example.com",
  "password": "motdepasse",
  "name": "Nom Prénom"
}

// Réponse 201
{
  "id": 1,
  "email": "user@example.com",
  "name": "Nom Prénom"
}
```

---

## Administration — `/admin`

> Tous les endpoints `/admin` nécessitent le rôle `admin`.

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/admin/users` | Lister tous les utilisateurs |
| `GET` | `/admin/users/{id}` | Détail d'un utilisateur |
| `PUT` | `/admin/users/{id}/role` | Modifier le rôle d'un utilisateur |
| `DELETE` | `/admin/users/{id}` | Supprimer un compte |
| `GET` | `/admin/plugins` | Lister les plugins actifs |
| `POST` | `/admin/plugins/{name}/reload` | Recharger un plugin |
| `POST` | `/admin/plugins/{name}/disable` | Désactiver un plugin |
| `GET` | `/admin/plugins/{name}/logs` | Logs d'un plugin |
| `GET` | `/admin/plugins/{name}/stats` | Statistiques d'un plugin |

---

## Manager (Scheduler) — `/manager`

| Méthode | Route | Description | Auth requise |
|---------|-------|-------------|--------------|
| `GET` | `/manager/tasks` | Lister toutes les tâches planifiées | ✅ admin |
| `GET` | `/manager/tasks/{name}` | Détail et historique d'une tâche | ✅ admin |
| `POST` | `/manager/tasks/{name}/run` | Déclencher manuellement une tâche | ✅ admin |
| `DELETE` | `/manager/tasks/{name}` | Annuler une tâche planifiée | ✅ admin |
| `GET` | `/manager/health` | État global du scheduler | ✅ |

---

## Codes de réponse HTTP

| Code | Signification |
|------|--------------|
| `200` | Succès |
| `201` | Ressource créée |
| `400` | Données invalides (validation Pydantic) |
| `401` | Non authentifié (token manquant ou expiré) |
| `403` | Non autorisé (rôle insuffisant) |
| `404` | Ressource introuvable |
| `500` | Erreur interne du serveur |

---

## Documentation interactive

L'interface Swagger est disponible à :

- **Swagger UI** : `http://localhost:8000/docs`
- **ReDoc** : `http://localhost:8000/redoc`
- **OpenAPI JSON** : `http://localhost:8000/openapi.json`

Le schéma OpenAPI se met à jour automatiquement à chaque chargement ou rechargement de plugin.

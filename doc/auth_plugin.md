# 🔐 Plugin d'Authentification (AuthPlugin)

Le plugin `AuthPlugin` fournit une solution d'authentification et d'autorisation de niveau industriel, intégrée au framework XCore.

## 🚀 Fonctionnalités

* **Gestion des utilisateurs** : Inscription, connexion (JWT), déconnexion, profil.
* **RBAC (Role-Based Access Control)** : Rôles (admin, user, etc.) et permissions fines par ressource.
* **Multi-provider** : Support extensif pour Google et GitHub (OAuth2).
* **Sessions** : Gestion des Refresh Tokens pour des sessions persistantes.
* **Sécurité** : Hashing sécurisé avec Argon2/Bcrypt.
* **RPC Inter-plugin** : Autres plugins peuvent vérifier les permissions via `call_plugin`.

## 🛠️ Configuration

Dans votre `xcore.yaml` :

```yaml
plugins:
  auth_plugin:
    secret_key: "votre-cle-secrete"
    access_token_expire_minutes: 30
    providers:
      github:
        client_id: "${GITHUB_CLIENT_ID}"
        client_secret: "${GITHUB_CLIENT_SECRET}"
      google:
        client_id: "${GOOGLE_CLIENT_ID}"
        client_secret: "${GOOGLE_CLIENT_SECRET}"
```

## 🌐 Endpoints API (FastAPI)

Le plugin expose automatiquement les routes suivantes sous `/plugins/auth_plugin/` :

| Méthode | Route | Description |
| :--- | :--- | :--- |
| POST | `/register` | Inscription d'un nouvel utilisateur |
| POST | `/login` | Authentification (retourne Access + Refresh Token) |
| POST | `/refresh` | Renouvellement de l'Access Token via Refresh Token |
| POST | `/logout` | Invalidation du Refresh Token |
| GET | `/me` | Informations sur l'utilisateur connecté (requiert JWT) |

## 🧩 Utilisation inter-plugin (RPC)

Les autres plugins peuvent utiliser les services d'authentification directement via `handle` :

```python
# Dans un autre plugin
result = await self.call_plugin(
    "auth_plugin",
    "check_permission",
    {"user_id": 42, "resource": "billing.invoices", "action": "read"}
)

if result.get("allowed"):
    # Accès autorisé
```

## 🛡️ Schéma de données

Le plugin gère les tables suivantes :
* `auth_users` : Utilisateurs principaux.
* `auth_roles` : Rôles disponibles.
* `auth_permissions` : Permissions par ressource/action.
* `auth_user_providers` : Liaison OAuth2 (Google/GitHub).
* `auth_user_sessions` : Stockage des Refresh Tokens.

## 🔑 Sécurité avancée

* **Hashing** : Utilise `passlib` avec Argon2 pour stocker les mots de passe.
* **JWT** : Signé avec la `secret_key` définie en configuration.
* **Rotation** : Supporte l'invalidation des sessions côté serveur.

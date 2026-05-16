# Décisions Techniques et Choix d'Architecture XCore

Ce document répertorie les décisions architecturales structurantes prises lors du développement de XCore v2 et leurs justifications techniques.

---

## 1. Isolation par Sous-processus (Sandboxing)

**Décision** : Utiliser `multiprocessing` / `subprocess` pour isoler les plugins tiers plutôt que des conteneurs (Docker) ou des threads.

### Pourquoi ce choix ?
- **Performance vs Isolation** : Les conteneurs ajoutent un overhead de démarrage et de gestion important. Les threads Python partagent le même GIL (Global Interpreter Lock), ce qui signifie qu'un plugin gourmand en CPU bloquerait tout le framework.
- **Robustesse** : Un sous-processus permet une isolation mémoire et CPU totale. Un crash dans un plugin sandboxed ne fait pas tomber le framework principal.
- **Simplicité de Déploiement** : Aucun démon externe n'est requis ; XCore gère lui-même le cycle de vie des processus.

---

## 2. Sécurité via Monkey-patching (FilesystemGuard)

**Décision** : Utiliser le monkey-patching dynamique des built-ins de Python au démarrage du worker.

### Pourquoi ce choix ?
- **Universalité** : Cela permet de sécuriser du code Python standard sans forcer les développeurs à utiliser des APIs de fichiers spécifiques. Les appels classiques à `open()` ou `Path.open()` deviennent sécurisés par défaut.
- **Fail-Closed** : Le guard est installé avant tout chargement de code plugin, garantissant qu'aucune évasion n'est possible dès les premières lignes d'exécution.

---

## 3. Communication via Flux Standards (IPC stdin/stdout)

**Décision** : Utiliser les pipes standards (stdin/stdout) pour l'IPC entre le Noyau et le Sandbox.

### Pourquoi ce choix ?
- **Compatibilité** : Ne nécessite pas d'ouvrir de sockets réseau, de gérer des ports ou des permissions de socket UNIX.
- **Simplicité du Protocole** : JSON-RPC sur flux de lignes (`\n`) est extrêmement simple à implémenter, à parser et à déboguer.
- **Performance** : Les pipes anonymes sont très performants pour l'échange de petits messages JSON (latence de l'ordre de la microseconde).

---

## 4. Middleware Pipeline Pré-compilé

**Décision** : Compiler la chaîne de middlewares en une seule fermeture (closure) imbriquée au démarrage du framework.

### Pourquoi ce choix ?
- **Optimisation Drastique** : Élimine le besoin de parcourir une liste de middlewares et de créer des lambdas à chaque appel de plugin.
- **Lisibilité vs Performance** : Permet de garder une écriture modulaire pour les développeurs de middlewares (Tracing, Auth, RateLimit) tout en ayant les performances d'un code monolithique à l'exécution.

---

## 5. Algorithme de Kahn pour les Dépendances

**Décision** : Utiliser un tri topologique basé sur l'algorithme de Kahn pour ordonner le chargement des plugins.

### Pourquoi ce choix ?
- **Détection des Cycles** : Garantit mathématiquement qu'aucune dépendance cyclique ne peut bloquer le système au démarrage.
- **Vagues de Chargement** : Permet de charger les plugins par "vagues" de nœuds indépendants, facilitant l'initialisation et la propagation des services.

---

## 6. Services Singleton et Propagation

**Décision** : Utiliser un conteneur de services centralisé (`ServiceContainer`) avec un dictionnaire partagé injecté dans les plugins Trusted.

### Pourquoi ce choix ?
- **Efficacité Mémoire** : Évite de multiplier les connexions aux bases de données ou à Redis ; tous les plugins partagent les mêmes instances de services.
- **Modularité** : Permet à un plugin d'exposer de nouveaux services (ex: un moteur de recherche `ext.search`) à tout le framework de manière dynamique.

---

## 7. Multi-Tenancy Transparent via Service Wrappers

**Décision** : Implémenter l'isolation multi-tenant en wrappant les services existants (cache, DB, scheduler) avec des proxies qui injectent automatiquement le `tenant_id`, plutôt qu'un registre de tenants centralisé.

### Pourquoi ce choix ?
- **Zéro changement de code plugin** : Un plugin qui écrit `cache.get("invoices")` fonctionne identiquement en mono-tenant et en multi-tenant. L'isolation est totalement transparente.
- **Graduelle et configurable** : Chaque dimension d'isolation (`isolate_cache`, `isolate_db`, `isolate_scheduler`) est un flag indépendant dans `integration.yaml`. On peut activer l'isolation cache sans toucher à la DB.
- **Pas de registre de tenants** : xcore ne maintient pas de liste de tenants valides. Le `tenant_id` vient du header HTTP, du sous-domaine, ou du `default_tenant`. Cela évite un service stateful supplémentaire et laisse la validation métier aux plugins.
- **Wrapping auto des adapters nommés** : `wrap_services_for_tenant()` détecte par nom de classe tous les adapters DB (`AsyncSQLAdapter`, `MongoDBAdapter`…) et les wrappe sans configuration explicite.

---

## 8. IPC Deny-by-Default avec `allowed_callers`

**Décision** : Autoriser les appels plugin-à-plugin via une whitelist déclarative dans `plugin.yaml` (`allowed_callers`), avec un refus par défaut si la liste est absente ou vide.

### Pourquoi ce choix ?
- **Fail-closed** : Un plugin nouvellement créé sans `allowed_callers` ne peut pas être appelé via IPC par un autre plugin. La sécurité est active dès le démarrage, sans configuration supplémentaire.
- **Déclaratif** : Chaque plugin est seul responsable de sa liste d'accès. Pas de configuration centralisée à maintenir — la policy vit avec le code du plugin.
- **Position dans le pipeline** : `IPCAuthMiddleware` est le premier middleware de la chaîne, avant Tracing, RateLimit et Permissions. Un appel refusé ne consomme aucun quota et ne génère aucune trace (uniquement un log WARNING).
- **Découplé du HTTP** : `caller=None` (appel HTTP direct) passe toujours — seuls les appels IPC plugin-à-plugin sont soumis à cette règle.

---

## 9. `@schema` comme Source Unique de Vérité

**Décision** : Fusionner le décorateur `@schema` (registre de schémas) et `@validate_payload` (validation Pydantic) en un seul décorateur — le dict `input` sert à la fois à documenter et à valider.

### Pourquoi ce choix ?
- **Duplication éliminée** : Avant la fusion, le développeur devait déclarer les champs deux fois — une fois dans `@schema(input=...)` pour la documentation, une fois dans un modèle Pydantic pour la validation. Toute divergence créait silencieusement un décalage entre la doc et le comportement réel.
- **Semver des schémas** : Le `version` dans `@schema` permet de détecter les breaking changes via `xcore plugin validate --check-breaking schemas_v1.json`. Un champ supprimé ou dont le type a changé est signalé automatiquement.
- **Opt-out possible** : `validate=False` désactive la validation automatique pour les cas où le plugin gère la validation manuellement ou reçoit des payloads dynamiques.

---

## 10. Minimalisme des Dépendances et Sécurité "Side-Channel"

**Décision** : Éviter les dépendances cryptographiques en pur Python et réduire l'empreinte du noyau au strict nécessaire.

### Pourquoi ce choix ?
- **Immunité aux Attaques Temporelles** : Suite à la vulnérabilité Minerva (CVE-2024-23342), nous avons retiré `python-jose` et `python-ecdsa`. XCore délègue désormais les opérations sensibles à des bibliothèques robustes basées sur C/OpenSSL (comme `cryptography` via `PyJWT`) si l'utilisateur choisit de les installer.
- **Surface d'Attaque Réduite** : En supprimant les bibliothèques inutilisées (Pillow, Watchdog, etc.) du noyau, nous limitons les vecteurs d'exploitation potentiels.
- **Vitesse de Boot** : Moins de dépendances signifie un temps d'importation Python plus court et un démarrage du framework plus rapide.

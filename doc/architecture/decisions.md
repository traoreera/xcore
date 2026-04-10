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

# Glossaire

Définitions des termes utilisés dans xcore et cette documentation.

---

**APIRouter**  
Objet FastAPI qui regroupe un ensemble de routes HTTP. Chaque plugin xcore expose ses routes via un `APIRouter` monté dynamiquement dans l'application principale.

---

**BackgroundTask**  
Mécanisme FastAPI permettant d'exécuter une fonction après l'envoi de la réponse HTTP, sans bloquer le client. Utilisé par xcore pour les tâches différées (envoi d'email, notifications, etc.).

---

**Extension / Service**  
Composant transversal situé dans `extensions/services/` qui fournit une fonctionnalité partagée entre plusieurs plugins (authentification, base de données, cache, etc.). Ne expose pas de routes HTTP.

---

**Hot Reload**  
Mécanisme de xcore qui permet de recharger un plugin modifié sans redémarrer le serveur. Le `Reloader` détecte les changements de fichiers et remonte automatiquement les routes dans FastAPI.

---

**JWT (JSON Web Token)**  
Standard ouvert pour l'échange sécurisé d'informations entre parties. xcore l'utilise pour l'authentification des utilisateurs. Un token JWT est signé avec la `secret_key` de la configuration.

---

**Loader (PluginLoader)**  
Composant du Manager (`manager/plManager/loader.py`) responsable de la découverte, du chargement et du montage dynamique des plugins. Il gère aussi la purge du cache Python (`sys.modules`) lors du hot reload.

---

**Manager**  
Orchestrateur central de xcore qui coordonne le `PluginLoader`, le `Scheduler`, et les services core. Il gère le cycle de vie complet de l'application.

---

**OTP (One-Time Password)**  
Code à usage unique, valide pour une durée limitée. Utilisé par xcore pour l'authentification à deux facteurs ou la validation d'actions sensibles.

---

**Plugin**  
Module Python autonome situé dans `plugins/` qui étend l'API de l'application via des routes FastAPI. Un plugin doit respecter un contrat précis : `PLUGIN_INFO`, classe `Plugin`, et `router`. Voir [Anatomie d'un plugin](./reference/plugin-anatomy.md).

---

**PLUGIN_INFO**  
Dictionnaire Python obligatoire dans `run.py` de chaque plugin. Il déclare les métadonnées du plugin (version, auteur, préfixe API, tags Swagger). Utilisé par le `Validator` pour vérifier la conformité du plugin.

---

**Poetry**  
Gestionnaire de dépendances et d'environnements virtuels Python utilisé par xcore. Remplace `pip + virtualenv + setup.py`.

---

**Pydantic**  
Bibliothèque Python de validation de données utilisée par FastAPI et xcore. Les schémas de données des routes sont définis avec des classes Pydantic (`BaseModel`).

---

**Sandbox**  
Environnement d'isolation dans lequel un plugin peut être exécuté avec des quotas de ressources (CPU, mémoire, timeout). Protège le serveur principal contre les plugins défectueux ou malveillants.

---

**Scheduler**  
Composant de xcore qui gère l'exécution de tâches planifiées (périodiques ou ponctuelles). Accessible via les endpoints `/manager/tasks`. Voir [Concepts du Scheduler](./concepts/scheduler-concepts.md).

---

**SemVer (Semantic Versioning)**  
Convention de versioning sous la forme `MAJOR.MINOR.PATCH` (ex: `1.2.0`). Utilisée pour versionner les plugins xcore.

---

**SQLAlchemy**  
ORM (Object-Relational Mapper) Python utilisé par xcore pour interagir avec la base de données. Les modèles sont définis comme des classes Python héritant de `Base`.

---

**Swagger / OpenAPI**  
Standard de documentation d'API REST. xcore génère automatiquement un schéma OpenAPI accessible sur `/docs` (Swagger UI) et `/redoc`. Le schéma est mis à jour à chaque chargement de plugin.

---

**Validator**  
Composant du Manager (`manager/plManager/validator.py`) qui vérifie qu'un plugin respecte le contrat xcore avant de le charger. Vérifie la présence de `PLUGIN_INFO`, de la classe `Plugin`, du `router`, et la cohérence des métadonnées.

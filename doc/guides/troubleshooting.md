# Guide de Dépannage (Troubleshooting) XCore

Ce guide vous aide à diagnostiquer et résoudre les erreurs courantes lors de l'utilisation de XCore.

---

## 1. Erreurs de Chargement de Plugins

### Symptôme : "Plugin '<name>' not found" ou "FileNotFoundError"
- **Cause** : Le plugin n'est pas dans le répertoire configuré (`./plugins` par défaut).
- **Solution** : Vérifiez le paramètre `plugins.directory` dans votre fichier `xcore.yaml`.

### Symptôme : "AttributeError: Classe Plugin() manquante"
- **Cause** : Votre fichier d'entry point (ex: `src/main.py`) ne définit pas de classe nommée `Plugin`.
- **Solution** : Assurez-vous d'avoir `class Plugin(TrustedBase): ...` dans votre code source.

### Symptôme : "ValueError: Boucle de dépendance détectée"
- **Cause** : Deux plugins ou plus dépendent l'un de l'autre de manière cyclique (ex: A -> B et B -> A).
- **Solution** : Revoyez la section `requires` de vos manifestes `plugin.yaml` pour briser la boucle.

---

## 2. Erreurs de Sandbox (Sandboxing)

### Symptôme : "PermissionError: [sandbox] ... interdit"
- **Cause** : Un plugin en mode `sandboxed` tente d'accéder à un fichier hors de son dossier `data/` ou d'importer un module interdit (ex: `os`, `sys`).
- **Solution** :
    - Vérifiez si le plugin peut passer en mode `trusted` (si vous avez confiance en la source).
    - Ajoutez le chemin nécessaire dans `allowed_paths` dans `plugin.yaml`.
    - Supprimez l'importation interdite du code source.

### Symptôme : "TimeoutError: Plugin call timed out"
- **Cause** : Le plugin prend trop de temps à répondre (boucle infinie, opération bloquante).
- **Solution** : Augmentez `resources.timeout_seconds` dans le manifeste ou optimisez le code du plugin.

### Symptôme : "MemoryError" ou crash du worker
- **Cause** : Le plugin a dépassé la limite de mémoire RAM allouée.
- **Solution** : Augmentez `resources.max_memory_mb` dans `plugin.yaml`.

---

## 3. Erreurs de Services (DB, Cache)

### Symptôme : "KeyError: Service 'db' indisponible"
- **Cause** : Le service de base de données n'est pas configuré ou a échoué lors de son initialisation.
- **Solution** :
    - Vérifiez la section `services.databases` dans `xcore.yaml`.
    - Consultez les logs pour voir l'erreur exacte de connexion (ex: "Connection refused").

### Symptôme : "OperationalError: (psycopg2.OperationalError) server closed the connection"
- **Cause** : La connexion à PostgreSQL a été interrompue ou le pool de connexions est saturé.
- **Solution** : Augmentez `pool_size` et `max_overflow` dans la configuration de la base de données.

---

## 4. Problèmes de l'API HTTP (FastAPI)

### Symptôme : "401 Unauthorized" sur les routes `/ipc`
- **Cause** : La clé API fournie dans l'entête `X-Plugin-Key` est incorrecte ou manquante.
- **Solution** : Vérifiez la valeur de `app.secret_key` dans `xcore.yaml` et assurez-vous qu'elle correspond à votre entête.

### Symptôme : "404 Not Found" sur les routes de plugins
- **Cause** : Le plugin n'est pas de type `Trusted` ou n'implémente pas `get_router()`.
- **Solution** : Seuls les plugins `trusted` peuvent exposer des routes HTTP personnalisées.

---

## 5. Comment obtenir de l'aide ?

Si votre problème n'est pas listé ici :

1. **Augmentez le niveau de logs** : Réglez `logging.level` sur `DEBUG` dans `xcore.yaml` pour voir les traces détaillées.
2. **Consultez les issues GitHub** : Recherchez des problèmes similaires sur le dépôt [XCore GitHub](https://github.com/traoreera/xcore/issues).
3. **Utilisez la CLI Health** : Exécutez `xcore health` pour un diagnostic complet de l'état du système.

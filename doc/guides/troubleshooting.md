# Guide de Dépannage (Troubleshooting)

Ce guide répertorie les erreurs courantes rencontrées lors du développement et du déploiement avec XCore, ainsi que leurs résolutions.

## Problèmes liés au Sandbox

### 1. PermissionError: Accès au fichier refusé
**Symptôme** : Un plugin en mode `sandboxed` lève une `PermissionError` lors d'une opération de lecture ou écriture.
**Cause** : Le `FilesystemGuard` bloque l'accès car le chemin n'est pas dans le dossier `data/` du plugin ou n'est pas autorisé dans le manifeste.
**Solution** :
- Vérifiez que vous utilisez bien des chemins relatifs au dossier `data/`.
- Ajoutez le chemin dans la section `filesystem.allowed_paths` du `plugin.yaml`.
- Utilisez `self.ctx.plugin_dir / "data"` pour construire vos chemins.

### 2. ImportError: Module 'os' (ou autre) interdit
**Symptôme** : Le plugin refuse de se charger avec une erreur d'import.
**Cause** : L' `ASTScanner` a détecté un import interdit pour le mode sandbox.
**Solution** :
- Retirez l'import incriminé.
- Si le module est indispensable et sûr, ajoutez-le à la `whitelist` dans `xcore.yaml` (nécessite un accès administrateur au noyau).
- Utilisez les services fournis par XCore (ex: utilisez le service `db` plutôt que d'importer un driver SQL directement).

### 3. Timeout d'action
**Symptôme** : L'appel à un plugin retourne une erreur de timeout.
**Cause** : L'exécution dépasse `resources.timeout_seconds`.
**Solution** :
- Optimisez votre code (boucles infinies, requêtes lourdes).
- Augmentez le timeout dans le manifeste si l'opération est légitimement longue.
- Déléguez l'opération au `scheduler` pour un traitement asynchrone.

## Problèmes de Chargement des Plugins

### 1. Signature Invalid
**Symptôme** : Le plugin `trusted` ne se charge pas.
**Cause** : La signature dans `plugin.sig` ne correspond pas au contenu du dossier ou la clé secrète est différente de celle du serveur.
**Solution** :
- Resignez le plugin avec `xcore plugin sign`.
- Vérifiez la variable d'environnement `XCORE_SIGNING_KEY` sur le serveur.

### 2. Dependency Not Found
**Symptôme** : Erreur de dépendance au démarrage.
**Cause** : Le plugin requiert un autre plugin qui n'est pas installé ou n'a pas pu démarrer.
**Solution** :
- Vérifiez la liste des plugins chargés avec `xcore plugin list`.
- Vérifiez l'ordre de chargement (topological sort) dans les logs.

## Performance et Stabilité

### 1. "Port already in use" (8000)
**Symptôme** : Le serveur XCore refuse de démarrer.
**Cause** : Une instance précédente n'a pas été arrêtée proprement.
**Solution** : `kill $(lsof -t -i :8000)` ou changez le port dans la configuration.

### 2. Consommation mémoire élevée du Sandbox
**Symptôme** : Le processus worker est tué par l'OS (OOM Killer).
**Cause** : Le plugin dépasse `max_memory_mb`.
**Solution** :
- Vérifiez les fuites de mémoire dans le code du plugin.
- Augmentez la limite dans `resources.max_memory_mb`.

## Debugging

### Logs détaillés
Pour voir ce qui se passe réellement dans le pipeline de middleware ou le sandbox, passez le niveau de log à `DEBUG` dans `xcore.yaml`.

### Utilisation du mode Sandbox pour le Debug
Même pour un plugin destiné au mode `trusted`, testez-le d'abord en mode `sandboxed`. Si le `FilesystemGuard` ou l' `ASTScanner` lève une erreur, cela indique souvent une pratique qui pourrait être optimisée ou sécurisée.

## Erreurs de Configuration (YAML)

### Interpolation de variables
**Symptôme** : `${VAR}` n'est pas remplacé.
**Cause** : La variable d'environnement n'est pas définie au moment du lancement.
**Solution** : Vérifiez votre fichier `.env` ou exportez la variable manuellement (`export VAR=value`).

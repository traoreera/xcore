# Sécurité et Isolation des Plugins XCore

XCore a été conçu pour exécuter du code tiers en garantissant la stabilité et la sécurité du système hôte grâce à un moteur de Sandboxing performant et multicouches.

---

## 1. Moteur de Sandboxing (Mode `sandboxed`)

Lorsqu'un plugin est configuré en mode `sandboxed`, il s'exécute dans un processus Python **totalement distinct**. Cette isolation garantit qu'un crash mémoire ou CPU du plugin n'affectera pas le framework central.

### Les 4 Couches de Protection du `FilesystemGuard`

XCore implémente une protection proactive via le `FilesystemGuard` qui monkey-patche dynamiquement les fonctions sensibles de Python au démarrage du sous-processus.

#### Couche 1 : Système de Fichiers (Isolation Path)
Intercepte `open()`, `os.open()`, `pathlib.Path.open()` et les syscalls associés.
- **Fail-closed** : Tout accès hors du dossier `data/` du plugin est bloqué par défaut.
- **Whitelist** : Seuls les chemins déclarés dans `allowed_paths` sont accessibles.

#### Couche 2 : Exécution Dynamique (Bloqueur de Code)
Désactive les fonctions permettant l'exécution de code non contrôlé :
- `eval()`, `exec()`, `compile()` et `input()` sont levés en `PermissionError`.

#### Couche 3 : Imports Critiques (Whitelist Modules)
Bloque l'importation de modules Python dangereux au niveau de `sys.meta_path` :
- `os`, `sys`, `subprocess`, `shutil`, `ctypes`, `threading`, `multiprocessing` sont proscrits.

#### Couche 4 : Accès Bas Niveau (Ctypes/Libc)
Bloque les appels directs à la bibliothèque `ctypes` pour empêcher le plugin de contourner les protections Python via des appels C directs vers la `libc` ou l'API C de Python.

---

## 2. Analyse Statique via `ASTScanner`

Avant même l'exécution, XCore scanne le code source de tous les plugins (`trusted` et `sandboxed`) à la recherche de patterns suspects.

- **Vérification de l'Entry Point** : Garantit que le code exécuté se trouve bien à l'intérieur du répertoire du plugin.
- **Scan des Imports** : Bloque les tentatives d'importation de modules interdits dès la phase de parsing de l'arbre syntaxique (AST).
- **Attributs Interdits** : Empêche l'accès aux attributs internes de Python comme `__class__`, `__globals__`, ou `__subclasses__` qui pourraient être utilisés pour l'évasion de sandbox.

---

## 3. Communication Inter-Processus (IPC)

La communication entre le Noyau (Kernel) et le bac à sable (Sandbox) s'effectue via un canal IPC sécurisé :

- **Protocole** : JSON-RPC léger sur flux `stdin` / `stdout`.
- **Sens unique** : Le plugin sandboxé ne peut jamais initier de commande vers le Kernel (modèle Pull/Response).
- **Limites de taille** : Les messages dépassant 512 Ko sont rejetés pour prévenir les attaques par déni de service (DoS) mémoire.

---

## 4. Limites de Ressources (RLIMIT)

Pour éviter qu'un plugin ne sature les ressources du serveur hôte, XCore applique des limites strictes au niveau du système d'exploitation :

- **Mémoire (RAM)** : Limite via `resource.RLIMIT_AS` (paramètre `max_memory_mb` dans le manifeste).
- **Temps d'exécution (CPU)** : Timeout forcé sur chaque appel IPC (paramètre `timeout_seconds`).
- **Débit (Rate Limiting)** : Contrôle du nombre d'appels par minute via le `MiddlewarePipeline`.

---

## 5. Signature et Vérification des Plugins

Pour les environnements de production, XCore supporte la signature cryptographique des plugins :

```bash
# Signer un plugin (génère un fichier signature.json)
xcore plugin sign ./plugins/mon_plugin --key MA_CLE_PRIVEE

# Vérifier la validité avant chargement
xcore plugin verify ./plugins/mon_plugin --key MA_CLE_PUBLIQUE
```

Un plugin dont la signature est invalide ou manquante sera rejeté par le framework si le mode `strict_trusted` est activé dans `xcore.yaml`.

---

## Bonnes Pratiques de Sécurité

1. **Privilégier le mode `sandboxed`** pour tout code n'étant pas issu d'une source interne de confiance.
2. **Utiliser des identifiants (UID) uniques** pour chaque plugin afin de garantir des namespaces d'import distincts dans `sys.modules`.
3. **Limiter les permissions** au strict nécessaire (ex: autoriser uniquement `cache.*` au lieu de `*`).
4. **Surveiller les logs de violation** : Toute tentative de violation de sandbox est logguée avec une stack trace complète pour audit.

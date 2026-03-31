# Référence de la CLI XCore

Le framework XCore est livré avec une interface en ligne de commande puissante pour gérer le cycle de vie des plugins, la sécurité et les services.

## Utilisation Générale

```bash
xcore [OPTIONS] COMMAND [ARGS]...
```

**Options Globales :**
- `--config PATH` : Chemin vers le fichier `xcore.yaml` (par défaut : cherche dans le dossier courant).
- `--version` : Affiche la version de xcore.

---

## Commandes des Plugins (`plugin`)

Gestion complète des extensions.

### `list`
Liste tous les plugins installés et leur état actuel.
```bash
xcore plugin list
```

### `load`
Charge dynamiquement un plugin sur un serveur en cours d'exécution.
```bash
xcore plugin load <name> [--host HOST] [--port PORT] [--path PREFIX] [--key API_KEY]
```

### `reload`
Recharge à chaud (Hot-reload) un plugin.
```bash
xcore plugin reload <name>
```

### `install`
Installe un nouveau plugin depuis différentes sources.
```bash
xcore plugin install <name> [--source {zip,git,marketplace}] [--url URL]
```

### `remove`
Supprime un plugin et ses fichiers associés.
```bash
xcore plugin remove <name>
```

### `info`
Affiche les métadonnées détaillées d'un plugin (version, auteur, permissions, etc.).
```bash
xcore plugin info <name>
```

### `sign`
Génère une signature de sécurité (`plugin.sig`) pour un plugin Trusted.
```bash
xcore plugin sign <path> --key <secret_key>
```

### `verify`
Vérifie l'intégrité et la signature d'un plugin.
```bash
xcore plugin verify <path> --key <secret_key>
```

### `validate`
Effectue une validation syntaxique et structurelle du manifeste `plugin.yaml`.
```bash
xcore plugin validate <path>
```

### `health`
Exécute un diagnostic de santé sur tous les plugins chargés (vérification AST, ressources).
```bash
xcore plugin health
```

---

## Commandes du Sandbox (`sandbox`)

Outils de débogage et d'inspection pour l'isolation.

### `run`
Lance un plugin en mode sandbox isolé pour tester son comportement sans démarrer tout le framework.
```bash
xcore sandbox run <name>
```

### `limits`
Affiche les limites de ressources (Mémoire, Disque, CPU, Rate Limit) configurées pour un plugin.
```bash
xcore sandbox limits <name>
```

### `fs`
Affiche et valide la politique d'accès au système de fichiers (Allowed/Denied paths).
```bash
xcore sandbox fs <name>
```

### `network`
Affiche la politique réseau du sandbox pour le plugin.
```bash
xcore sandbox network <name>
```

---

## Commandes du Marketplace (`marketplace`)

Interaction avec le catalogue officiel de plugins XCore.

### `list`
Liste les plugins disponibles sur le marketplace.
```bash
xcore marketplace list
```

### `search`
Recherche un plugin par mot-clé.
```bash
xcore marketplace search <query>
```

### `show`
Affiche les détails d'un plugin du marketplace, incluant les notes et commentaires.
```bash
xcore marketplace show <name>
```

### `trending`
Affiche les plugins les plus populaires du moment.
```bash
xcore marketplace trending
```

### `rate`
Note un plugin (score de 1 à 5).
```bash
xcore marketplace rate <name> --score <1-5>
```

---

## Commandes Système et Santé

### `services status`
Vérifie l'état de connexion et la santé des services de base (Base de données, Cache, Scheduler).
```bash
xcore services status [--json]
```

### `health`
Effectue un check-up global du système (Kernel, Services, Plugins).
```bash
xcore health [--json]
```

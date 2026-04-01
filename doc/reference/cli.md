# Référence du CLI XCore

Le CLI `xcore` est le point d'entrée unique pour la gestion du framework.

## Commandes Plugin

### `xcore plugin list`
Liste tous les plugins installés sur l'instance courante.

### `xcore plugin load <name>`
Charge un plugin dynamiquement sur un serveur en cours d'exécution.
- `--host` : Host du serveur (défaut: 127.0.0.1)
- `--port` : Port du serveur (défaut: 8000)
- `--path` : Préfixe du router
- `--key` : Clé API secrète

### `xcore plugin health`
Effectue un check de santé (scan AST et vérification de manifeste) pour tous les plugins.

### `xcore plugin install <name>`
Installe un nouveau plugin.
- `--source` : `marketplace`, `git`, `zip`
- `--url` : URL directe pour Git ou ZIP

### `xcore plugin sign <path>`
Signe un plugin `trusted` avec une clé secrète pour garantir son intégrité.
- `--key` : Clé secrète de signature

### `xcore plugin validate <path>`
Valide le fichier `plugin.yaml` d'un répertoire donné.

## Commandes Sandbox

### `xcore sandbox run <name>`
Lance un plugin en mode isolé pour tester son comportement en environnement restreint.

### `xcore sandbox limits <name>`
Affiche les limites de ressources configurées (CPU, Mémoire, Disque) pour un plugin.

### `xcore sandbox fs <name>`
Affiche la politique de système de fichiers (dossiers autorisés/interdits).

### `xcore sandbox network <name>`
Affiche la politique réseau autorisée pour le plugin.

## Commandes Marketplace

### `xcore marketplace search <query>`
Recherche des plugins par nom ou mot-clé.

### `xcore marketplace trending`
Liste les plugins les plus populaires.

### `xcore marketplace show <name>`
Affiche les métadonnées complètes d'un plugin du catalogue.

### `xcore marketplace rate <name> --score <1-5>`
Envoie une note pour un plugin.

## Commandes Services & Santé

### `xcore services status [--json]`
Affiche l'état de tous les services core (Base de données, Cache, Scheduler, etc.).

### `xcore health [--json]`
Effectue un bilan de santé global de l'instance XCore.
- `--json` : Format de sortie machine-readable.

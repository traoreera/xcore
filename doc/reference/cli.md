# Manuel de la CLI XCore

La CLI `xcore` est l'outil en ligne de commande pour gérer le framework, les plugins et les services.

---

## 1. Commandes Globales

```bash
# Voir la version installée
xcore --version

# Afficher l'aide générale
xcore --help

# Spécifier un fichier de configuration personnalisé
xcore --config /chemin/vers/xcore.yaml <commande>
```

---

## 2. Gestion des Plugins (`xcore plugin`)

| Commande | Usage | Description |
|----------|-------|-------------|
| **`list`** | `xcore plugin list` | Affiche tous les plugins installés et leur statut. |
| **`health`** | `xcore plugin health` | Vérifie la santé de tous les plugins chargés. |
| **`load`** | `xcore plugin load <name>` | Charge un plugin dynamiquement. |
| **`reload`** | `xcore plugin reload <name>` | Recharge un plugin (Hot-reload). |
| **`remove`** | `xcore plugin remove <name>` | Désinstalle un plugin du répertoire `./plugins`. |
| **`info`** | `xcore plugin info <name>` | Affiche les métadonnées détaillées du plugin. |
| **`validate`** | `xcore plugin validate <path>`| Vérifie la syntaxe du manifeste et du code source. |
| **`sign`** | `xcore plugin sign <path>` | Signe cryptographiquement un plugin Trusted. |
| **`verify`** | `xcore plugin verify <path>` | Vérifie la signature cryptographique du plugin. |

---

## 3. Gestion du Bac à Sable (`xcore sandbox`)

Le mode sandbox permet d'exécuter et de tester des plugins dans un environnement isolé sans lancer tout le framework XCore.

| Commande | Usage | Description |
|----------|-------|-------------|
| **`run`** | `xcore sandbox run <name>` | Lance le plugin en mode isolé pour test. |
| **`limits`** | `xcore sandbox limits <name>` | Affiche les limites (mémoire, CPU) du plugin. |
| **`fs`** | `xcore sandbox fs <name>` | Affiche la politique du système de fichiers (Allowed/Denied). |
| **`network`**| `xcore sandbox network <name>`| Affiche la politique réseau du plugin. |

---

## 4. Marketplace (`xcore marketplace`)

Interagit avec le catalogue de plugins public XCore.

| Commande | Usage | Description |
|----------|-------|-------------|
| **`list`** | `xcore marketplace list` | Affiche tous les plugins du catalogue. |
| **`search`** | `xcore marketplace search <query>`| Recherche des plugins par mot-clé. |
| **`trending`**| `xcore marketplace trending` | Affiche les plugins populaires. |
| **`show`** | `xcore marketplace show <name>` | Détails techniques d'un plugin. |
| **`rate`** | `xcore marketplace rate <name>` | Donne une note au plugin (1 à 5). |

---

## 5. État des Services (`xcore services`)

Vérifie la santé de l'infrastructure commune.

| Commande | Usage | Description |
|----------|-------|-------------|
| **`status`** | `xcore services status` | Affiche l'état des connexions DB, Cache, etc. |
| **`health`** | `xcore health` | Lance un diagnostic global du framework. |

---

## Options d'affichage

La plupart des commandes supportent l'option `--json` pour faciliter l'intégration avec d'autres outils (ex: `jq`).

```bash
# Récupérer la liste des plugins en JSON
xcore plugin list --json | jq '.[].name'
```

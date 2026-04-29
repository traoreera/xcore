# CLI Reference

Le CLI `xcore` expose des commandes pour gérer les plugins, le sandbox, le marketplace et l'état du système.

```bash
poetry run xcore --help
poetry run xcore --version
```

---

## `xcore plugin`

### `list`

Liste tous les plugins installés dans le répertoire configuré.

```bash
poetry run xcore plugin list
```

### `info <name>`

Affiche les métadonnées détaillées d'un plugin (version, mode, auteur, permissions).

```bash
poetry run xcore plugin info mon_plugin
```

### `load <name>`

Charge un plugin sur le serveur en cours d'exécution via l'API interne.

```bash
poetry run xcore plugin load mon_plugin [--host 127.0.0.1] [--port 8000] [--key <api_key>]
```

### `reload <name>`

Recharge à chaud un plugin sans redémarrer le serveur.

```bash
poetry run xcore plugin reload mon_plugin
```

### `install <name>`

Installe un plugin depuis le marketplace, un fichier zip ou un dépôt git.

```bash
# Depuis le marketplace (défaut)
poetry run xcore plugin install auth_plugin

# Depuis une archive zip
poetry run xcore plugin install mon_plugin --source zip --url https://example.com/plugin.zip

# Depuis git
poetry run xcore plugin install mon_plugin --source git --url https://github.com/user/plugin
```

### `remove <name>`

Supprime un plugin du répertoire.

```bash
poetry run xcore plugin remove mon_plugin
```

### `sign <path>`

Génère une signature HMAC-SHA256 (`plugin.sig`) pour un plugin Trusted.

```bash
poetry run xcore plugin sign plugins/mon_plugin --key "ma_cle_secrete"
```

### `verify <path>`

Vérifie la signature d'un plugin.

```bash
poetry run xcore plugin verify plugins/mon_plugin --key "ma_cle_secrete"
```

### `validate <path>`

Valide le manifeste d'un plugin (structure, types, compatibilité framework).

```bash
poetry run xcore plugin validate plugins/mon_plugin
```

### `health`

Vérifie l'état de santé de tous les plugins.

```bash
poetry run xcore plugin health
```

---

## `xcore sandbox`

### `run <name>`

Lance un plugin dans un processus sandbox isolé.

```bash
poetry run xcore sandbox run mon_plugin
```

### `limits <name>`

Affiche les limites de ressources configurées (mémoire, timeout, rate limit).

```bash
poetry run xcore sandbox limits mon_plugin
```

### `network <name>`

Affiche la politique réseau du plugin sandboxed.

```bash
poetry run xcore sandbox network mon_plugin
```

### `fs <name>`

Affiche la politique filesystem (chemins autorisés/interdits).

```bash
poetry run xcore sandbox fs mon_plugin
```

---

## `xcore marketplace`

### `list`

Liste tous les plugins disponibles sur le marketplace.

```bash
poetry run xcore marketplace list
```

### `trending`

Affiche les plugins populaires.

```bash
poetry run xcore marketplace trending
```

### `search <query>`

Recherche des plugins par mot-clé.

```bash
poetry run xcore marketplace search "authentication"
```

### `show <name>`

Affiche les détails d'un plugin du marketplace.

```bash
poetry run xcore marketplace show auth_plugin
```

### `rate <name> --score <1-5>`

Note un plugin.

```bash
poetry run xcore marketplace rate auth_plugin --score 5
```

---

## `xcore services status`

Affiche l'état de tous les services (DB, Cache, Scheduler).

```bash
poetry run xcore services status
poetry run xcore services status --json
```

---

## `xcore health`

Health check global du système.

```bash
poetry run xcore health
poetry run xcore health --json
```

---

## Options globales

| Option | Description |
|:-------|:------------|
| `--config <path>` | Chemin vers `xcore.yaml` (défaut : auto-détection) |
| `--version` | Affiche la version (`xcore v2.1.2`) |

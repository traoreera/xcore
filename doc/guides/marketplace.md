# Marketplace XCore

Le Marketplace XCore est le catalogue centralisé pour découvrir, installer et partager des plugins.

## Configuration

Le client marketplace se configure dans votre fichier `xcore.yaml` :

```yaml
marketplace:
  url: https://marketplace.xcore.dev   # URL de base de l'API
  api_key: "${XCORE_MARKETPLACE_KEY}"  # Clé API (optionnelle pour la lecture)
  timeout: 10                          # Timeout des requêtes en secondes
  cache_ttl: 300                       # Durée du cache local en secondes
```

## Utilisation via le CLI

Le CLI XCore permet d'interagir directement avec le marketplace.

### Découverte

Rechercher des plugins :
```bash
xcore marketplace search "auth"
```

Afficher les plugins populaires :
```bash
xcore marketplace trending
```

Voir les détails d'un plugin :
```bash
xcore marketplace show "auth-provider"
```

### Installation

L'installation peut se faire depuis différentes sources :

```bash
# Depuis le marketplace officiel (par défaut)
xcore plugin install auth-provider

# Depuis un dépôt Git
xcore plugin install my-plugin --source git --url https://github.com/user/my-plugin.git

# Depuis une archive ZIP
xcore plugin install custom-tool --source zip --url https://example.com/plugin.zip
```

## Client SDK

Vous pouvez également utiliser le client marketplace dans votre code :

```python
from xcore.marketplace.client import MarketplaceClient
from xcore.configurations.loader import XcoreConfig

config = XcoreConfig("xcore.yaml")
client = MarketplaceClient(config)

# Rechercher des plugins
results = await client.search("database")

# Récupérer un plugin spécifique
plugin = await client.get_plugin("postgres-connector")

# Noter un plugin
await client.rate_plugin("postgres-connector", score=5)
```

## Publication (Bientôt)

La publication de plugins sur le marketplace officiel nécessite un compte et une clé API.
Les plugins doivent passer une validation de sécurité (AST Scan) avant d'être acceptés.

### Processus de validation
1. **Analyse Statique** : Scan AST pour détecter les imports interdits.
2. **Vérification du Manifeste** : Validation du fichier `plugin.yaml`.
3. **Signature** : Les plugins Trusted doivent être signés avec une clé reconnue.

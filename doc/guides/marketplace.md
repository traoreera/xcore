# XCore Marketplace : Catalogue de Plugins

Le Marketplace XCore est l'endroit centralisé pour découvrir, installer et gérer des plugins tiers pour votre instance XCore.

---

## 1. Concepts du Marketplace

Le Marketplace agit comme un index public de plugins. Chaque plugin est vérifié et scanné pour garantir sa compatibilité avec XCore.

- **Dépôt de Plugins** : Les plugins sont hébergés sur le Marketplace (ZIP) ou sur des plateformes Git (GitHub, GitLab).
- **Versioning** : Support complet du versioning sémantique pour garantir la stabilité de votre application lors des mises à jour.
- **Sécurité** : Les plugins téléchargés depuis le Marketplace s'exécutent par défaut en mode `sandboxed`.

---

## 2. Utilisation via la CLI XCore

La CLI est le moyen privilégié pour interagir avec le Marketplace.

### Rechercher des plugins

```bash
# Lister tous les plugins disponibles
xcore marketplace list

# Rechercher par mot-clé ou catégorie
xcore marketplace search "authentication"

# Voir les plugins les plus populaires
xcore marketplace trending
```

### Consulter les détails

```bash
# Afficher les métadonnées complètes d'un plugin
xcore marketplace show auth_plugin
```

### Noter et Commenter

```bash
# Donner une note de 1 à 5 à un plugin
xcore marketplace rate auth_plugin --score 5
```

---

## 3. Installation de Plugins

Vous pouvez installer des plugins directement depuis le Marketplace ou depuis des sources externes.

### Installation depuis le Marketplace

```bash
# Installation automatique (téléchargement et extraction dans /plugins)
xcore plugin install auth_plugin
```

### Installation depuis une source Git

```bash
# Cloner un dépôt Git directement dans le dossier plugins
xcore plugin install --source git --url https://github.com/user/my_plugin.git
```

### Installation depuis un fichier ZIP

```bash
# Installer depuis une archive locale ou distante
xcore plugin install --source zip --url https://example.com/plugin.zip
```

---

## 4. Configuration du Client Marketplace

Pour utiliser votre propre index de plugins ou configurer une clé API, modifiez la section `marketplace` de votre fichier `xcore.yaml` :

```yaml
marketplace:
  url: "https://marketplace.xcore.dev" # URL de l'API du Marketplace
  api_key: "${XCORE_MARKETPLACE_KEY}" # Votre clé API (optionnel)
  timeout: 10                          # Timeout des requêtes en secondes
  cache_ttl: 300                       # Durée de cache des résultats (secondes)
```

---

## 5. Publier votre Plugin sur le Marketplace

Si vous souhaitez partager votre plugin avec la communauté :

1. Assurez-vous que votre plugin respecte la structure standard (voir [Guide de création](creating-plugins.md)).
2. Validez le manifeste avec `xcore plugin validate`.
3. Soumettez votre plugin via l'interface web du Marketplace ou l'API de publication (en cours de développement).

---

## Bonnes Pratiques

1. **Vérifier les avis** : Avant d'installer un plugin tiers, consultez sa note et ses commentaires sur le Marketplace.
2. **Utiliser le Sandboxing** : Exécutez toujours les plugins tiers en mode `sandboxed` pour une sécurité maximale.
3. **Épingler les versions** : Pour vos environnements de production, spécifiez toujours une version exacte lors de l'installation pour éviter les ruptures de compatibilité.

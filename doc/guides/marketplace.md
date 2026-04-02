# Guide du Marketplace

Le Marketplace XCore est l'endroit centralisé pour découvrir, partager et installer des extensions pour vos applications XCore.

## Introduction

Le Marketplace permet de :
- Parcourir des centaines de plugins vérifiés.
- Installer des extensions en une seule commande.
- Partager vos propres créations avec la communauté.
- Bénéficier de mises à jour automatiques.

## Parcourir le Marketplace

### Lister les plugins
Pour voir les plugins disponibles :
```bash
xcore marketplace list
```

### Rechercher une extension
Vous cherchez une fonctionnalité spécifique (ex: authentification, redis) ?
```bash
xcore marketplace search "auth"
```

### Voir les tendances
Découvrez ce que la communauté utilise le plus :
```bash
xcore marketplace trending
```

## Détails et Notation

Avant d'installer, vous pouvez consulter les détails d'un plugin :
```bash
xcore marketplace show users-auth
```

Vous y trouverez :
- La description complète.
- Les permissions requises.
- Les dépendances.
- Le score moyen des utilisateurs.

### Noter un plugin
Si vous appréciez un plugin, faites-le savoir :
```bash
xcore marketplace rate users-auth --score 5
```

## Installation de Plugins

L'installation via le marketplace est le mode par défaut de la commande `install`.

### Installation simple
```bash
xcore plugin install my-awesome-plugin
```

XCore va :
1. Télécharger le package depuis le marketplace.
2. Vérifier l'intégrité.
3. Résoudre et installer les dépendances nécessaires.
4. Valider le manifeste.

## Publication (Aperçu)

*Note : La publication nécessite un compte sur le portail développeur XCore.*

Pour publier un plugin :
1. Assurez-vous que votre `plugin.yaml` est complet.
2. Testez votre plugin en local avec `xcore plugin validate`.
3. Signez votre plugin si nécessaire.
4. Utilisez le portail web pour soumettre votre archive ZIP ou lier votre dépôt GitHub.

## Sécurité du Marketplace

Chaque plugin soumis au marketplace subit un processus de validation :
- **Scan Malware** : Analyse des fichiers.
- **Scan AST** : Détection automatique des patterns de code dangereux.
- **Vérification de Version** : Compatibilité garantie avec les versions de framework déclarées.

Nous recommandons d'utiliser le **Execution Mode: Sandboxed** pour tout plugin tiers dont vous n'avez pas audité le code source.

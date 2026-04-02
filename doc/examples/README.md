# Exemples de Plugins

Découvrez des exemples concrets pour apprendre à développer avec XCore.

## Catalogue d'exemples

Les exemples suivants sont disponibles pour illustrer les différentes facettes du framework :

1.  **[Basic Plugin](basic-plugin.md)** : Un plugin minimaliste pour comprendre les bases (cycle de vie, actions simple).
2.  **[Complete Plugin](complete-plugin.md)** : Un exemple exhaustif utilisant la base de données, le cache, les événements et les routes HTTP.
3.  **[Trusted Plugin](trusted-plugin.md)** : Un plugin s'exécutant dans le processus principal avec un accès complet aux services.
4.  **[Sandboxed Plugin](sandboxed-plugin.md)** : Un plugin isolé dans un sous-processus avec des restrictions de sécurité et de ressources.

## Structure recommandée

Pour tous vos plugins, nous recommandons de suivre cette structure de dossiers :

```text
my_plugin/
├── plugin.yaml          # Manifeste du plugin
├── plugin.sig           # Signature (pour le mode Trusted strict)
├── requirements.txt     # Dépendances Python (si non incluses dans le noyau)
├── data/                # Données locales (seul dossier accessible en Sandbox)
└── src/                 # Code source
    ├── __init__.py
    ├── main.py          # Point d'entrée défini dans plugin.yaml
    ├── models.py        # Modèles Pydantic ou SQLAlchemy
    ├── services.py      # Logique métier interne
    └── utils.py         # Fonctions utilitaires
```

## Bonnes pratiques illustrées

Dans ces exemples, vous trouverez l'application des principes suivants :

-   **Validation forte** via Pydantic pour toutes les entrées.
-   **Gestion d'erreurs standardisée** utilisant les helpers `ok()` et `error()`.
-   **Utilisation asynchrone** systématique pour ne pas bloquer l'event loop.
-   **Découplage** via le bus d'événements pour la communication inter-plugins.
-   **Observabilité** via l'injection de logs et de métriques.

---

### Vous ne trouvez pas ce que vous cherchez ?

-   Consultez le **[Guide de création de plugins](../guides/creating-plugins.md)** pour un tutoriel pas à pas.
-   Référez-vous au **[SDK Reference](../reference/sdk.md)** pour la liste complète des APIs.
-   Visitez le **[Marketplace](../guides/marketplace.md)** pour voir des plugins réels publiés par la communauté.

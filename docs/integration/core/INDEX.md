# Module Integration Core

Le module **Integration Core** contient les orchestrateurs et registres de bas niveau du framework de services.

## Fichiers

```{toctree}
:maxdepth: 1

integration
events
registry
```

## Contribution

- Le coeur doit rester indépendant des services spécifiques.
- Assurez-vous que le `ServiceRegistry` supporte les accès par clé et par type.
- Ne surchargez pas `Integration` ; déléguez la logique aux services dédiés.

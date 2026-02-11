# Guide de Contribution

Merci de votre intérêt pour contribuer à xcore ! Ce document décrit les processus et conventions pour contribuer au projet.

## Table des Matières

1. [Code de Conduite](#code-de-conduite)
2. [Comment Contribuer](#comment-contribuer)
3. [Configuration du Développement](#configuration-du-développement)
4. [Standards de Code](#standards-de-code)
5. [Processus de Pull Request](#processus-de-pull-request)
6. [Signaler des Bugs](#signaler-des-bugs)
7. [Proposer des Fonctionnalités](#proposer-des-fonctionnalités)

## Code de Conduite

Ce projet adopte un code de conduite simple :

- Soyez respectueux et constructif
- Acceptez les critiques constructives
- Concentrez-vous sur ce qui est meilleur pour la communauté
- Ne tolérez aucun harcèlement

## Comment Contribuer

### Signaler des Problèmes

Avant de créer une issue :

1. Vérifiez qu'elle n'existe pas déjà
2. Utilisez les templates d'issue fournis
3. Fournissez autant de détails que possible

### Soumettre des Modifications

1. **Fork** le repository
2. **Clone** votre fork
3. **Créez** une branche (`git checkout -b feature/nom-feature`)
4. **Committez** vos changements (`git commit -am 'Add feature'`)
5. **Push** vers la branche (`git push origin feature/nom-feature`)
6. **Ouvrez** une Pull Request

## Configuration du Développement

### Prérequis

- Python 3.11+
- Poetry 1.7+
- Git

### Installation Locale

```bash
# Cloner le repository
git clone https://github.com/votre-repo/xcore.git
cd xcore

# Installer les dépendances
poetry install

# Activer l'environnement
poetry shell

# Configurer pre-commit
pre-commit install

# Créer la base de données
createdb xcore_dev

# Exécuter les migrations
alembic upgrade head

# Lancer le serveur de développement
uvicorn main:app --reload
```

### Tests

```bash
# Exécuter tous les tests
pytest

# Avec couverture
pytest --cov=xcore --cov-report=html

# Tests spécifiques
pytest tests/test_auth.py

# Tests avec débogage
pytest --pdb
```

### Qualité du Code

```bash
# Linter
ruff check .

# Formatter
black .

# Imports
isort .

# Type checking
mypy xcore/

# Tout en une fois
pre-commit run --all-files
```

## Standards de Code

### Style Python

Nous utilisons PEP 8 avec quelques modifications :

- **Longueur de ligne**: 100 caractères maximum
- **Guillemets**: Double quotes pour les strings
- **Docstrings**: Format Google

Exemple :

```python
def ma_fonction(param1: str, param2: int = 10) -> bool:
    """Description courte de la fonction.

    Description plus détaillée si nécessaire.
    Peut s'étendre sur plusieurs lignes.

    Args:
        param1: Description du premier paramètre.
        param2: Description du second paramètre avec valeur par défaut.

    Returns:
        Description de la valeur de retour.

    Raises:
        ValueError: Quand la condition X se produit.

    Example:
        >>> ma_fonction("test", 5)
        True
    """
    if param1 == "":
        raise ValueError("param1 ne peut pas être vide")
    return len(param1) > param2
```

### Nommage

| Type | Convention | Exemple |
|------|------------|---------|
| Modules | minuscule_avec_underscores | `mon_module.py` |
| Classes | PascalCase | `MaClasse` |
| Fonctions | minuscule_avec_underscores | `ma_fonction()` |
| Variables | minuscule_avec_underscores | `ma_variable` |
| Constantes | MAJUSCULES_AVEC_UNDERSCORES | `MA_CONSTANTE` |
| Enumérations | PascalCase | `MonEnum` |
| Exceptions | PascalCase + Error | `MonErreur` |

### Imports

Organisez les imports en trois groupes séparés par une ligne vide :

```python
# 1. Imports standard
import os
import sys
from datetime import datetime
from typing import Optional, List

# 2. Imports tierces
from fastapi import FastAPI, Depends
from sqlalchemy import Column, Integer
from pydantic import BaseModel

# 3. Imports locaux
from database import get_db
from auth.models import User
from config import settings
```

### Types

Utilisez les annotations de type partout :

```python
from typing import Optional, Union

# Bon
async def get_user(user_id: int) -> Optional[User]:
    pass

# Mauvais
async def get_user(user_id):
    pass
```

### Gestion des Erreurs

```python
# Bon
try:
    result = await operation_risquee()
except SpecificException as e:
    logger.error(f"Opération échouée: {e}")
    raise CustomError("Message clair") from e

# Mauvais
try:
    result = await operation_risquee()
except:
    pass  # Ne jamais faire ça !
```

## Processus de Pull Request

### Avant de Soumettre

- [ ] Les tests passent
- [ ] La couverture de tests est maintenue
- [ ] Le code est formaté avec Black
- [ ] Les imports sont triés
- [ ] Pas de regressions détectées par le linter
- [ ] Documentation mise à jour si nécessaire

### Description de la PR

Incluez :

1. **Quoi**: Description des changements
2. **Pourquoi**: Raison des changements
3. **Comment**: Approche technique
4. **Tests**: Comment tester les changements

Template :

```markdown
## Description

Description des changements apportés.

## Type de Changement

- [ ] Bug fix
- [ ] Nouvelle fonctionnalité
- [ ] Breaking change
- [ ] Documentation

## Tests

- [ ] Tests unitaires ajoutés
- [ ] Tests d'intégration ajoutés
- [ ] Tests manuels effectués

## Checklist

- [ ] Mon code suit les standards du projet
- [ ] J'ai vérifié que mes changements ne causent pas de régressions
- [ ] J'ai mis à jour la documentation si nécessaire
```

### Revue de Code

- Minimum 1 approbation requise
- Tous les checks CI doivent passer
- Les commentaires doivent être résolus
- Pas de commits de debug (`print`, `console.log`)

## Signaler des Bugs

### Template de Bug Report

```markdown
**Description**
Description claire du bug.

**Pour Reproduire**
1. Allez à '...'
2. Cliquez sur '...'
3. Voyez l'erreur

**Comportement Attendu**
Ce qui devrait se passer.

**Comportement Actuel**
Ce qui se passe réellement.

**Screenshots**
Si applicable, ajoutez des screenshots.

**Environnement**
- OS: [ex: Ubuntu 22.04]
- Python: [ex: 3.11]
- Version xcore: [ex: 1.0.0]
- Navigateur: [si applicable]

**Logs**
```
Traceback (most recent call last):
  ...
```

**Contexte Additionnel**
Tout autre information utile.
```

## Proposer des Fonctionnalités

### Template de Feature Request

```markdown
**Description**
Description de la fonctionnalité souhaitée.

**Problème Résolu**
Quel problème cette fonctionnalité résout-elle ?

**Solution Proposée**
Description de la solution envisagée.

**Alternatives Considérées**
Autres approches possibles.

**Contexte Additionnel**
Maquettes, exemples d'utilisation, etc.
```

## Documentation

### Documentation de Code

Documentez :
- Les modules publics
- Les classes et méthodes publiques
- Les fonctions complexes
- Les paramètres et retours

### Documentation Utilisateur

Mettez à jour `docs/source/` si vous ajoutez :
- Nouvelles fonctionnalités
- Changements d'API
- Nouveaux plugins

### Documentation des Plugins

Chaque plugin doit inclure :
- README.md avec description
- Documentation des routes API
- Guide d'installation
- Exemples d'utilisation

## Sécurité

### Signalement de Vulnérabilités

**Ne créez pas d'issue publique** pour les vulnérabilités de sécurité.

Envoyez un email à : security@example.com

Incluez :
- Description de la vulnérabilité
- Étapes de reproduction
- Impact potentiel
- Suggestions de correction (optionnel)

### Bonnes Pratiques de Sécurité

- Ne commitez jamais de secrets
- Utilisez des requêtes paramétrées
- Validez toutes les entrées
- Échappez les sorties HTML
- Utilisez HTTPS en production

## Communauté

### Canaux de Communication

- **GitHub Discussions**: Questions générales
- **GitHub Issues**: Bugs et features
- **Discord**: Discussion en temps réel
- **Email**: Contact direct

### Reconnaissance

Les contributeurs seront :
- Mentionnés dans le README
- Listés dans les release notes
- Ajoutés au fichier CONTRIBUTORS.md

## Licence

En contribuant, vous acceptez que vos contributions soient sous la même licence MIT que le projet.

## Questions ?

N'hésitez pas à ouvrir une issue pour toute question sur la contribution.

---

Merci de contribuer à xcore ! 🎉

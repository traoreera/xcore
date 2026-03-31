# Guide du Contributeur

Nous sommes ravis que vous souhaitiez contribuer à XCore ! Ce guide vous explique comment configurer votre environnement et soumettre vos changements.

## Configuration de l'Environnement de Développement

### 1. Cloner le dépôt
```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

### 2. Installer les dépendances
Nous utilisons **Poetry** pour la gestion des dépendances.
```bash
poetry install
```

### 3. Installer les hooks de pré-commit
Pour garantir la qualité du code (linting, formatage) avant chaque commit :
```bash
poetry run pre-commit install
```

## Workflow de Développement

### Créer une branche
Utilisez des noms de branches descriptifs :
- `feat/nom-de-la-fonctionnalite`
- `fix/nom-du-bug`
- `docs/mise-a-jour-doc`

```bash
git checkout -b feat/nouvelle-api-plugin
```

### Formatage et Style
Nous suivons strictement les conventions suivantes :
- **Black** pour le formatage automatique.
- **isort** pour l'organisation des imports.
- **flake8** pour le linting.

Pour formater automatiquement votre code :
```bash
make lint-fix
```

### Tests Unitaires
Tout nouveau code doit être accompagné de tests.
```bash
# Lancer tous les tests
make test

# Lancer avec couverture de code
make test-coverage
```

## Conventions de Commit

Nous utilisons le format **Conventional Commits** :
- `feat:` : Une nouvelle fonctionnalité.
- `fix:` : Une correction de bug.
- `docs:` : Changement dans la documentation.
- `style:` : Changement cosmétique (espaces, formatage).
- `refactor:` : Modification du code sans changement de comportement.
- `test:` : Ajout ou modification de tests.
- `chore:` : Tâches de maintenance (dépendances, build).

Exemple : `feat(kernel): ajout du support pour les middlewares personnalisés`

## Processus de Pull Request (PR)

1. **Vérifiez votre code** : Assurez-vous que les tests passent et que le linting est propre.
2. **Documentez** : Si vous ajoutez une fonctionnalité, mettez à jour les fichiers dans `/doc`.
3. **Soumettez** : Poussez votre branche et ouvrez une PR sur GitHub.
4. **Révision** : Un mainteneur passera en revue vos changements. Soyez prêt à effectuer des ajustements si nécessaire.

### Critères d'acceptation d'une PR :
- Les tests CI passent.
- La couverture de code n'a pas diminué de manière significative.
- Le code respecte l'architecture "Plugin-First".
- La documentation est à jour (en français et en anglais si possible).

## Amélioration de la Documentation

La documentation est située dans le dossier `/doc`. Elle est générée par **MkDocs**.
Pour prévisualiser vos changements localement :
```bash
poetry run mkdocs serve
```

---

Merci de contribuer à faire de XCore le meilleur framework de plugins pour Python !

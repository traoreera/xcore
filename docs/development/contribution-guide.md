# Guide de contribution

Merci de vouloir contribuer à xcore ! Ce guide explique le processus complet pour proposer des changements.

---

## Avant de commencer

1. **Forkez** le repository sur GitHub
2. Lisez l'[architecture](../architecture.md) pour comprendre la structure du projet
3. Consultez les [issues ouvertes](https://github.com/traoreera/xcore/issues) pour éviter les doublons
4. Pour les grosses fonctionnalités, ouvrez d'abord une issue pour en discuter

---

## Mise en place de l'environnement

```bash
# Cloner votre fork
git clone https://github.com/VOTRE_USERNAME/xcore.git
cd xcore
git checkout features

# Installer les dépendances (y compris dev)
poetry install

# Vérifier que les tests passent
make test
```

---

## Workflow de contribution

### 1. Créer une branche

```bash
# Toujours partir de la branche `features`
git checkout features
git pull origin features

# Nommer la branche selon le type de changement
git checkout -b feature/nom-de-la-fonctionnalite
git checkout -b fix/description-du-bug
git checkout -b docs/section-documentee
git checkout -b refactor/composant-refactorise
```

### 2. Développer

Faites vos modifications en respectant le [style de code](./code-style.md).

Commitez régulièrement avec des messages clairs :

```bash
git add .
git commit -m "feat(plugins): ajoute le support des tâches async dans les plugins"
git commit -m "fix(auth): corrige la validation du token expiré"
git commit -m "docs(tutorials): ajoute tutoriel de création de service"
```

**Format des messages de commit** (Conventional Commits) :

```
type(scope): description courte

Corps optionnel expliquant le pourquoi du changement.

Fixes #123
```

Types : `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

### 3. Tester

```bash
# Lancer tous les tests
make test

# Lancer les tests d'un module spécifique
poetry run pytest tests/test_plugins.py -v

# Vérifier la couverture de code
poetry run pytest --cov=xcore --cov-report=html
```

Vos changements doivent maintenir la couverture de tests existante.

### 4. Vérifier le style

```bash
make lint     # Vérifier avec ruff
make format   # Formater avec black
```

### 5. Pousser et ouvrir une Pull Request

```bash
git push origin feature/nom-de-la-fonctionnalite
```

Sur GitHub, ouvrez une Pull Request vers la branche `features` avec :

- Un **titre clair** décrivant le changement
- Une **description** expliquant le contexte, les choix techniques, et les tests effectués
- La référence à l'issue liée (`Closes #123`)

---

## Types de contributions

### Corriger un bug

1. Reproduisez le bug avec un test qui échoue
2. Corrigez le bug
3. Vérifiez que le test passe
4. Vérifiez que les autres tests n'ont pas régressé

### Ajouter une fonctionnalité

1. Discutez de la feature dans une issue avant de coder
2. Implémentez la feature
3. Ajoutez des tests
4. Mettez à jour la documentation pertinente

### Améliorer la documentation

Les contributions à la doc sont très bienvenues ! Suivez la même structure de dossiers que ce guide.

### Contribuer un plugin

Les plugins de qualité peuvent être proposés dans le dossier `plugins/` ou dans un repository séparé listé dans la doc.

---

## Critères de revue

Votre PR sera révisée selon ces critères :

- ✅ Les tests passent
- ✅ Le code respecte le style du projet
- ✅ La logique est correcte et bien découpée
- ✅ La documentation est à jour si besoin
- ✅ Pas de régression sur les fonctionnalités existantes
- ✅ Les messages de commit sont clairs

---

## Questions et aide

- Ouvrez une [issue](https://github.com/traoreera/xcore/issues) pour toute question
- Mentionnez `@traoreera` dans votre PR pour une revue rapide

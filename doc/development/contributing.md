# Guide de Contribution XCore

Merci de l'intérêt que vous portez à XCore ! Nous accueillons avec enthousiasme les contributions de la communauté pour faire de ce framework la référence en matière de modularité Python.

---

## 1. Code de Conduite

Veuillez lire et respecter notre [Code de Conduite](https://github.com/traoreera/xcore/blob/main/CODE_OF_CONDUCT.md) pour garantir un environnement inclusif et respectueux pour tous.

---

## 2. Comment Contribuer ?

### Signaler des Bugs
Si vous trouvez un bug, veuillez ouvrir une [Issue GitHub](https://github.com/traoreera/xcore/issues) en fournissant :
- Une description claire du problème.
- Les étapes pour reproduire le bug.
- Votre environnement (OS, version de Python, version de XCore).

### Proposer des Fonctionnalités
Les idées sont les bienvenues ! Ouvrez une issue de type "Feature Request" pour en discuter avant d'entamer le développement.

### Soumettre une Pull Request (PR)
1. **Forkez** le dépôt.
2. **Créez une branche** pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`).
3. **Développez** votre code en suivant les standards du projet (Black, Flake8).
4. **Ajoutez des tests** unitaires et/ou d'intégration.
5. **Vérifiez** que tous les tests passent (`pytest`).
6. **Soumettez** votre PR avec une description détaillée.

---

## 3. Standards de Code

- **Formatage** : Nous utilisons `black` pour le formatage du code.
- **Imports** : Utilisez `isort` pour trier vos imports.
- **Typage** : Le code doit être typé (Type Hints) autant que possible pour faciliter la maintenance et l'aide à l'IDE.
- **Documentation** : Toute nouvelle fonction ou classe publique doit être documentée (style Google).

---

## 4. Environnement de Développement

```bash
# Installer Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Installer les dépendances
poetry install

# Lancer les tests
poetry run pytest
```

---

## 5. Processus de Revue

Chaque PR est revue par au moins un mainteneur du projet. Nous portons une attention particulière à :
- La clarté du code.
- La couverture des tests.
- L'impact sur les performances du Noyau (Kernel).
- La documentation associée.

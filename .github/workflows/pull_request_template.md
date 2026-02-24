## Description

<!-- Décris brièvement le changement et pourquoi il est nécessaire. -->

Closes #<!-- numéro de l'issue -->

---

## Type de changement

<!-- Coche les cases qui s'appliquent -->

- [ ] 🐛 Bug fix
- [ ] ✨ Nouvelle fonctionnalité
- [ ] 🔌 Nouveau plugin
- [ ] 📖 Documentation
- [ ] ♻️ Refactoring
- [ ] 🔒 Sécurité
- [ ] ⚡ Performance
- [ ] 🔧 CI / Configuration

---

## Checklist

- [ ] Mon code respecte le [style du projet](/docs/development/code-style.md)
- [ ] J'ai ajouté des tests qui couvrent mes changements
- [ ] Tous les tests existants passent (`make test`)
- [ ] J'ai mis à jour la documentation si nécessaire
- [ ] Le titre de la PR respecte le format Conventional Commits

---

## Comment tester

<!-- Décris les étapes pour tester ce changement localement -->

```bash
# Exemple
poetry install
uvicorn main:app --reload
curl http://localhost:8000/app/mon_plugin/
```

---

## Screenshots (si applicable)

<!-- Ajoute des captures d'écran si le changement affecte l'UI ou les routes -->

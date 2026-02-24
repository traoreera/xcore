# Introduction à xcore

Ce tutoriel vous guide de l'installation jusqu'à votre première API fonctionnelle avec un plugin custom.

**Durée estimée :** 15 minutes  
**Prérequis :** Python ≥ 3.13, connaissances de base de FastAPI

---

## Ce que vous allez construire

À la fin de ce tutoriel, vous aurez :
- xcore installé et fonctionnel
- Un plugin `hello_plugin` créé et monté automatiquement
- Une route `GET /app/hello/` qui répond en JSON
- Une compréhension du cycle de vie d'un plugin

---

## Étape 1 — Installer xcore

Clonez le repository et installez les dépendances avec Poetry :

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
git checkout features
poetry install
```

Vérifiez que l'installation fonctionne :

```bash
poetry run python -c "import fastapi; print('FastAPI OK')"
```

---

## Étape 2 — Lancer le serveur

```bash
uvicorn main:app --reload
```

Visitez `http://localhost:8000/docs`
## Résumé

Vous avez appris à :
- Installer et lancer xcore
**Prochaine étape :** [Créer un plugin complet](./plugin-creation.md) avec schémas Pydantic, gestion d'erreurs et tâches planifiées.

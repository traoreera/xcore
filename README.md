Parfait, je te fais un **README complet et professionnel** pour ton projet xcore, structuré pour être prêt à publier ou partager.

---

# xcore – Multi-Plugins Framework pour FastAPI

[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

xcore est un framework avancé pour **FastAPI**, conçu pour gérer dynamiquement des plugins, exécuter des tâches planifiées, isoler les plugins en sandbox, et fournir une interface complète d’administration et de monitoring.

---

## Table des matières

1. [Présentation](#présentation)
2. [Fonctionnalités principales](#fonctionnalités-principales)
3. [Installation](#installation)
4. [Structure du projet](#structure-du-projet)
5. [Développement des plugins](#développement-des-plugins)
6. [Administration](#administration)
7. [Scheduler & Tâches](#scheduler--tâches)
8. [Monitoring & Logs](#monitoring--logs)
9. [Sécurité](#sécurité)
10. [Contribution](#contribution)
11. [Licence](#licence)

---

## Présentation

xcore est conçu pour les environnements où il faut :

* Charger et exécuter des plugins FastAPI de manière dynamique.
* Isoler les plugins pour éviter qu’un plugin défectueux n’impacte le serveur.
* Planifier des tâches périodiques ou ponctuelles via un scheduler intégré.
* Fournir une interface d’administration et de monitoring complète pour les plugins et les tâches.

---

## Fonctionnalités principales

* **Chargement dynamique de plugins** avec purge du cache Python.
* **Hot reload** des plugins et des routes FastAPI, avec OpenAPI/Swagger automatiquement mis à jour.
* **Scheduler intégré** pour exécuter des tâches synchrones ou asynchrones.
* **Sandbox** pour limiter CPU, mémoire et temps d’exécution des plugins.
* **Monitoring** : logs centralisés, performance, statistiques par plugin et tâches.
* **Administration via API** : liste plugins, reload, état des tâches, logs.
* **Notifications & alertes** : échecs répétés des tâches ou plugins.
* **Versioning et configuration des plugins**.

---

## Installation

**Pré-requis :**

* Python ≥ 3.13
* FastAPI
* Uvicorn

**Installation :**

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
poetry install
```

**Lancer le serveur :**

```bash
uvicorn main:app --reload
```

---

## Structure du projet

```text
xcore/
 ├─ main.py                 # Point d’entrée FastAPI
 ├─ manager/                # Core framework
 │   ├─ plManager/
 │   │   ├─ loader.py       # Gestion des plugins
 │   │   ├─ reloader.py     # Reload des plugins à chaud
 │   │   ├─ installer.py    # Installation et validation
 │   │   ├─ repository.py   # Base de données / plugins actifs
 │   │   └─ validator.py    # Validation des plugins
 │   ├─ tools/              # Outils utilitaires
 │   └─ schemas/            # Schémas Pydantic
 ├─ plugins/                # Plugins dynamiques
 │   └─ example_plugin/
 │       ├─ __init__.py
 │       ├─ run.py
 │       └─ router.py
 └─ README.md
```

---

## Développement des plugins

**Structure minimale d’un plugin :**

```text
plugin_name/
 ├─ __init__.py
 ├─ run.py
 ├─ router.py
 └─ config.yaml
```

**Exemple de metadata dans `run.py` :**

```python
PLUGIN_INFO = {
    "version": "1.0.0",
    "author": "Nom Auteur",
    "Api_prefix": "/app/plugin_name",
    "tag_for_identified": ["plugin_name"],
}
```

**Route FastAPI dans `router.py` :**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/plugin_name", tags=["plugin_name"])

@router.get("/status")
async def status():
    return {"status": "ok"}
```

**Exécution du plugin :**

* Async ou sync via `concured()`
* Hot reload automatique et injection dans FastAPI via `Loader`

---

## Administration

**Endpoints principaux :**

| Endpoint                | Description                                            |
| ----------------------- | ------------------------------------------------------ |
| `/admin/plugins`        | Liste des plugins, version, statut actif/inactif       |
| `/admin/plugins/reload` | Reload dynamique des plugins et routes                 |
| `/admin/tasks`          | Liste et état des tâches planifiées                    |
| `/admin/logs`           | Logs centralisés des plugins et du core                |
| `/health`               | Vérification globale : DB, scheduler, plugins, sandbox |

---

## Scheduler & Tâches

* Tâches périodiques ou ponctuelles définies par les plugins.
* Support des priorités et dépendances entre tâches.
* Monitoring et alerting pour chaque tâche.

---

## Monitoring & Logs

* Logs centralisés par plugin et core.
* Statistiques : temps d’exécution, erreurs, nombre de tâches exécutées.
* Optionnel : intégration Prometheus/Grafana pour monitoring avancé.

---

## Sécurité

* Sandbox pour isoler les plugins (CPU/mémoire/timeouts).
* Limitation d’accès aux routes plugins via token ou OAuth2.
* Validation stricte des inputs des plugins exposés via API.

---

## Contribution

1. Forker le repository.
2. Créer une branche pour votre feature : `feature/xyz`.
3. Committer vos modifications : `git commit -m "Add feature xyz"`.
4. Pousser sur la branche : `git push origin feature/xyz`.
5. Ouvrir un Pull Request.

---

## Licence

MIT License – voir le fichier `LICENSE` pour plus de détails.

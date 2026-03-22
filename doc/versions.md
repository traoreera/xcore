# Versions de XCore

Cette page liste l'historique des versions du framework XCore, les changements majeurs et les notes de mise à jour.

## Version Actuelle

### XCore v2.0.0 (Stable)

**Date de sortie** : Mars 2025

**Statut** : ✅ Stable et recommandée

La version 2.0 est une refonte complète du framework avec une architecture plugin-first, un système de sandboxing renforcé et une intégration native des services.

#### Fonctionnalités principales

- **🏗️ Architecture Plugin-First** — Le noyau est minimal, toutes les fonctionnalités sont des plugins
- **🔒 Système de Sandboxing** — Exécution isolée des plugins avec restrictions AST et IPC
- **⚡ Intégration FastAPI native** — Les plugins peuvent exposer leurs propres routes HTTP
- **🔄 Hot Reloading** — Rechargement à chaud des plugins sans redémarrage serveur
- **📊 Observabilité intégrée** — Logs structurés, métriques Prometheus, tracing OpenTelemetry
- **🗄️ Multi-base de données** — Support PostgreSQL, MySQL, SQLite, MongoDB, Redis
- **⏰ Scheduler intégré** — APScheduler avec persistance Redis
- **🔐 Sécurité renforcée** — Signatures HMAC, permissions granulaires, rate limiting

#### Changements par rapport à v1.x

| Fonctionnalité | v1.x | v2.0 |
|----------------|------|------|
| Architecture | Monolithique | Plugin-first |
| Isolation | Processus basique | Sandboxing AST + IPC |
| Routes HTTP | Limité | Complet via `get_router()` |
| Types de plugins | Trusted uniquement | Trusted + Sandboxed |
| Configuration | Python-only | YAML + Environnement |
| Base de données | SQL uniquement | SQL + NoSQL + Cache |
| EventBus | Basique | Priorités + Hooks |
| Reloading | Manuel | Automatique (watchdog) |

#### Migration depuis v1.x

Voir le guide de migration détaillé dans [Migrations](#migration-depuis-v1x).

---

## Historique des versions

### v2.0.0 (2025-03-21)

**Nouveautés majeures**

- Refonte complète de l'architecture vers plugin-first
- Introduction du système de sandboxing avec isolation par processus
- Support des plugins Sandboxed via IPC
- Intégration complète de FastAPI avec montage automatique des routers
- ServiceContainer avec injection de dépendances typée
- EventBus avec priorités (HIGH, NORMAL, LOW)
- HookManager pour filtres et actions
- PermissionEngine pour contrôle d'accès granulaire
- RateLimiter par plugin avec configuration YAML
- Health checks intégrés pour tous les services
- Support Redis comme backend de cache et scheduler
- CLI complet (`xcore plugin`, `xcore sandbox`, `xcore services`)
- Auto-discovery et chargement automatique des plugins

**Breaking Changes**

- La classe `Plugin` de v1 est remplacée par `TrustedBase`
- Les imports ont changé : `from xcore import Xcore, TrustedBase`
- Le fichier de configuration passe de `config.py` à `xcore.yaml`
- Les plugins doivent maintenant définir un `plugin.yaml`

**Corrections**

- Isolation complète des plugins (pas de conflits de noms de modules)
- Gestion propre du cycle de vie (load/reload/unload)
- Memory leaks corrigés lors du rechargement

---

### v1.2.0 (2024-11-15)

**Nouveautés**

- Support Python 3.12
- Améliorations de performance du PluginLoader
- Nouvelles commandes CLI

**Corrections**

- Fuite mémoire dans le rechargement des plugins
- Race condition dans l'EventBus

---

### v1.1.0 (2024-08-20)

**Nouveautés**

- Support Redis pour le cache distribué
- Améliorations du système de logs
- Documentation MkDocs

**Corrections**

- Problème de connexion DB en async
- Timeout trop court pour certains plugins

---

### v1.0.0 (2024-06-01)

**Première version stable**

- Système de plugins basique
- Support PostgreSQL et SQLite
- EventBus simple
- Configuration par code Python
- CLI minimal

---

### v0.9.0-beta (2024-04-10)

**Version bêta initiale**

- Architecture de base
- Chargement dynamique de plugins
- Support FastAPI basique

---

## Feuille de route

### v2.1.0 (Prévue - Q2 2025)

**Fonctionnalités prévues**

- [ ] Marketplace de plugins intégré
- [ ] Support GraphQL pour les plugins
- [ ] WebSocket natif pour communication temps réel
- [ ] Autoscaling automatique des workers sandbox
- [ ] Dashboard web de monitoring

### v2.2.0 (Prévue - Q3 2025)

**Fonctionnalités prévues**

- [ ] Support gRPC pour communication inter-services
- [ ] Circuit breaker intégré
- [ ] Chiffrement de bout en bout pour IPC
- [ ] Plugin marketplace avec vérification automatique

### v3.0.0 (Prévue - 2026)

**Objectifs à long terme**

- Support WebAssembly pour plugins ultra-isolés
- Distributed XCore (cluster multi-nœuds)
- Machine Learning intégré pour auto-scaling

---

## Politique de support

| Version | Statut | Support jusqu'au |
|---------|--------|------------------|
| v2.0.x | ✅ Active | Mars 2026 |
| v1.2.x | 🛟 Maintenance | Juin 2025 |
| v1.1.x | ❌ Fin de vie | Novembre 2024 |
| v1.0.x | ❌ Fin de vie | Août 2024 |
| < v1.0 | ❌ Fin de vie | Juin 2024 |

**Légende** :

- ✅ **Active** — Reçoit toutes les corrections et nouvelles fonctionnalités
- 🛟 **Maintenance** — Corrections de sécurité uniquement
- ❌ **Fin de vie** — Plus de support, mise à jour recommandée

---

## Notes de publication détaillées

### XCore v2.0.0

#### Architecture Kernel

Le noyau XCore v2 est conçu autour de plusieurs composants clés :

```
XCore
├── PluginSupervisor      # Orchestration des plugins
├── ServiceContainer      # Gestion des services
├── EventBus             # Communication événementielle
├── HookManager          # Hooks et filtres
└── PluginRegistry       # Registre des plugins
```

#### Types de plugins

**Trusted Plugins**

- Exécution dans le processus principal
- Accès complet aux services
- Peuvent exposer des routes HTTP
- Signature HMAC requise en mode strict

**Sandboxed Plugins**

- Exécution dans processus isolé
- Restrictions AST sur les imports
- Communication via IPC
- Limites de ressources (mémoire, CPU, temps)

#### Services intégrés

| Service | Description | Configuration |
|---------|-------------|---------------|
| Database | SQL et NoSQL | `services.databases` |
| Cache | Memory ou Redis | `services.cache` |
| Scheduler | Tâches planifiées | `services.scheduler` |
| Extensions | Services custom | `services.extensions` |

#### Migration depuis v1.x

**Étape 1** : Mettre à jour les imports

```python
# v1.x
from xcore import Plugin

# v2.0
from xcore import TrustedBase
```

**Étape 2** : Créer le fichier `plugin.yaml`

```yaml
# plugin.yaml
name: mon_plugin
version: "2.0.0"
execution_mode: trusted
entry_point: src/main.py
```

**Étape 3** : Migrer la configuration

```yaml
# xcore.yaml (nouveau)
app:
  name: my-app
  env: production

plugins:
  directory: ./plugins

services:
  databases:
    default:
      type: postgresql
      url: "${DATABASE_URL}"
```

**Étape 4** : Adapter le cycle de vie

```python
# v1.x
class Plugin:
    def load(self):
        pass

# v2.0
class Plugin(TrustedBase):
    async def on_load(self):
        pass

    async def on_unload(self):
        pass
```

---

## Installation des versions spécifiques

### Via Poetry

```bash
# Dernière version
poetry add xcore

# Version spécifique
poetry add xcore@2.0.0

# Version avec contrainte
poetry add "xcore@^2.0"
```

### Via pip

```bash
# Dernière version
pip install xcore

# Version spécifique
pip install xcore==2.0.0

# Version minimale
pip install "xcore>=2.0.0"
```

### Via git

```bash
# Dernière version stable
git clone https://github.com/traoreera/xcore.git
cd xcore
poetry install

# Tag spécifique
git checkout v2.0.0
poetry install
```

---

## Signalement de problèmes

Si vous rencontrez des problèmes avec une version spécifique :

1. Consultez les [issues GitHub](https://github.com/traoreera/xcore/issues)
2. Vérifiez si le problème existe dans la dernière version
3. Créez une issue avec :
   - Version de XCore
   - Version de Python
   - Système d'exploitation
   - Description du problème
   - Code de reproduction

---

## Vérifier votre version

```python
import xcore

print(xcore.__version__)       # "2.0.0"
print(xcore.__version_info__)  # (2, 0, 0)
```

Via CLI :

```bash
poetry run xcore --version
# xcore v2.0.0
```

---

## Compatibilité

### Python

| XCore Version | Python 3.11 | Python 3.12 | Python 3.13 |
|---------------|-------------|-------------|-------------|
| v2.0.x | ✅ | ✅ | ✅ |
| v1.2.x | ✅ | ✅ | ⚠️ |
| v1.1.x | ✅ | ⚠️ | ❌ |
| v1.0.x | ✅ | ❌ | ❌ |

### Dépendances majeures

| XCore | FastAPI | SQLAlchemy | Pydantic |
|-------|---------|------------|----------|
| v2.0.x | 0.118+ | 2.0+ | 2.11+ |
| v1.2.x | 0.100+ | 1.4+ | 1.10+ |
| v1.1.x | 0.95+ | 1.4+ | 1.10+ |
| v1.0.x | 0.90+ | 1.3+ | 1.10+ |

---

## Contribuer

Pour contribuer au développement de XCore :

1. Fork le repository
2. Créez une branche feature (`git checkout -b feature/amazing`)
3. Committez vos changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing`)
5. Ouvrez une Pull Request

Voir le [guide de contribution](development/contributing.md) pour plus de détails.

---

*Dernière mise à jour de cette page : 21 Mars 2025*

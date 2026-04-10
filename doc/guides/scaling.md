# Mise à l'échelle (Scaling) de XCore

XCore a été conçu pour gérer des applications de production à haute performance tout en restant modulaire. Ce guide explique comment faire évoluer votre architecture XCore.

---

## 1. Mise à l'échelle Verticale (Scale Up)

L'architecture `plugin-first` permet de tirer parti de la puissance d'une seule machine en ajustant les paramètres système.

### Parallélisme des Plugins

XCore supporte nativement l'exécution concurrente des plugins.
- **Plugins Trusted** : Plusieurs appels peuvent être traités simultanément sur la même instance.
- **Plugins Sandboxed** : Chaque instance de plugin tourne dans son propre processus, permettant d'utiliser tous les cœurs du CPU du serveur hôte.

### Optimisation des Ressources

Ajustez les paramètres de `xcore.yaml` en fonction de la capacité de votre serveur :

```yaml
services:
  databases:
    default:
      pool_size: 20       # Nombre de connexions SQLAlchemy conservées
      max_overflow: 30    # Surplus de connexions autorisé lors des pics de charge
  cache:
    max_size: 5000       # Nombre d'entrées maximal en cache mémoire
```

---

## 2. Mise à l'échelle Horizontale (Scale Out)

Pour gérer des charges massives, vous pouvez déployer plusieurs instances de XCore derrière un équilibreur de charge (Load Balancer).

### Utilisation de Gunicorn / Uvicorn

Déployez XCore avec plusieurs workers HTTP (FastAPI) :

```bash
# Lancer 4 workers XCore gérés par Gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Services de Données Partagés

Lorsque vous avez plusieurs instances XCore, vous devez utiliser des backends de données centralisés :

```yaml
services:
  # Utilisez une base de données PostgreSQL centralisée
  databases:
    default:
      url: "postgresql+psycopg2://user:pass@db-cluster.local:5432/xcore"

  # Utilisez un serveur Redis centralisé pour le cache et le scheduler
  cache:
    backend: "redis"
    url: "redis://redis-cluster.local:6379/0"

  scheduler:
    backend: "redis"  # Partage les tâches planifiées entre les instances
```

---

## 3. Optimisation des Performances (Hot Paths)

XCore inclut des optimisations spécifiques pour les chemins d'exécution critiques (Hot Paths) :

- **Middleware Pré-compilé** : Le pipeline de middleware est compilé en fermetures (closures) lors de l'initialisation pour minimiser l'overhead par appel (~2µs par appel).
- **Cache de permissions** : Les évaluations de politiques RBAC sont mémoïsées pour éviter le re-calcul fréquent des regex de ressources.
- **Désactivation du Traçage** : En production, si le tracing n'est pas nécessaire, désactivez-le dans `xcore.yaml` pour gagner ~5-8% de performance sur les appels IPC.

---

## 4. Stratégies de Déploiement

### Déploiement via Docker

Utilisez l'image Docker officielle pour garantir un environnement stable et reproductible (voir le [Guide de déploiement](../deployment/guide.md)).

### Surveillance de la charge

Utilisez les endpoints de métriques (`/plugin/ipc/metrics`) avec un collecteur comme **Prometheus** pour surveiller :
- L'utilisation CPU/RAM des sous-processus de sandbox.
- Le temps de réponse moyen (P95/P99) des actions de plugins.
- Le nombre de violations de sandbox (tentatives de lecture hors du dossier `data/`).

---

## Résumé du Scaling

| Composant | Stratégie Verticale | Stratégie Horizontale |
|-----------|---------------------|-----------------------|
| **Plugins** | Augmenter CPU/RAM | Multiplier les instances XCore |
| **Bases de Données** | Augmenter le pool | Utiliser un cluster (Read Replicas) |
| **Cache / Bus** | Utiliser Redis local | Utiliser un cluster Redis (Sentinel/Cluster) |
| **Sandbox** | Optimiser `max_memory_mb` | Répartir les workers sur plusieurs nœuds |

# Scaling et Performance

XCore est conçu pour passer de l'expérimentation à la production massive. Ce guide détaille les stratégies de montée en charge et les optimisations de performance internes.

## Modèle de Threading et Concurrence

XCore combine plusieurs modèles pour maximiser l'utilisation des ressources :

- **Boucle d'événement Async (Main Process)** : Gère le serveur FastAPI, le routing et les plugins `trusted`.
- **Sous-processus isolés (Workers)** : Gère les plugins `sandboxed`, évitant ainsi que des calculs lourds ne bloquent la boucle d'événement principale.
- **Service Scheduler** : Gère les tâches de fond de manière asynchrone sans impacter le temps de réponse des APIs.

## Stratégies de Scaling Horizontal

### Déploiement Multi-Processus
Grâce à son architecture "Modular Monolith", XCore peut être déployé derrière un Load Balancer (Nginx, HAProxy) en plusieurs instances identiques.

**Recommandations pour le multi-instance :**
- **Sessions** : Utilisez le service `cache` avec un backend **Redis** pour partager l'état des sessions entre les instances.
- **Base de données** : Utilisez un pool de connexions robuste (configuré via `pool_size` dans `xcore.yaml`).
- **Events** : Pour un scaling massif, envisagez un bridge EventBus vers un broker de messages externe (RabbitMQ/Kafka).

## Optimisations de Performance Internes

### Pipeline de Middleware Pré-compilée
Dans `PluginSupervisor`, la chaîne de middleware (Tracing -> RateLimit -> Permissions -> Retry) n'est pas reconstruite à chaque appel. Elle est assemblée sous forme de fermetures (closures) imbriquées lors du boot, réduisant l'overhead d'appel de ~40%.

### Synchronous Rate Limiter
Le `RateLimiter` a été optimisé en supprimant les verrous asynchrones complexes au profit d'opérations atomiques en mémoire. Cette modification permet de traiter des milliers de vérifications par seconde avec une latence quasi nulle.

### État de Plugin Optimisé
Le passage de l'état du plugin par une machine à états stricte a été simplifié dans le "hot-path" (suppression de l'état `RUNNING`) pour permettre une exécution concurrente maximale sans verrouillage inutile.

## Monitoring du Scaling

Utilisez les métriques d'histogramme pour surveiller les centiles de latence (P95, P99). Si le P99 dépasse 500ms sur des plugins `trusted`, il est temps d'ajouter des instances ou d'optimiser les requêtes DB.

## Résilience (Circuit Breaker)

Bien que non inclus par défaut dans le noyau, il est fortement conseillé d'implémenter un pattern **Circuit Breaker** dans vos plugins qui appellent des APIs externes pour éviter les cascades de pannes (cascading failures).

```python
# Exemple de logique de protection
if self.consecutive_failures > threshold:
    self.circuit_open = True
    raise ServiceUnavailable("Circuit is open")
```

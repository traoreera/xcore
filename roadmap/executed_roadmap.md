# 🗺️ État d'avancement de la Roadmap XCore

Ce document présente l'état actuel du framework XCore par rapport aux objectifs définis dans la roadmap (V1 à V5).

## 📊 Résumé Global

| Version | Focus | État | Progression |
| :--- | :--- | :--- | :--- |
| **V1** | Fondation Kernel | **Terminé** | 100% |
| **V2** | Industrialisation | **Terminé** | 100% |
| **V3** | Distribution | **Avancé** | 25% |
| **V4** | Cloud Native | **Démarré** | 5% |
| **V5** | Intelligence Native | **Concept** | 0% |

---

## 🚀 V1 — Fondation du Kernel
**Objectif : Construire un framework plugin-first solide.**

| Fonctionnalité | État | Localisation / Note |
| :--- | :---: | :--- |
| Plugin Loader | ✅ | `xcore/kernel/runtime/loader.py` |
| Lifecycle Manager | ✅ | `xcore/kernel/runtime/lifecycle.py` |
| Service Container (DI) | ✅ | `xcore/services/container.py` |
| Plugin Manifest (`plugin.yaml`) | ✅ | `xcore/kernel/security/validation.py` |
| Trusted Plugins | ✅ | `xcore/kernel/runtime/activator.py` |
| Sandbox Plugins | ✅ | `xcore/kernel/sandbox/` |
| IPC interne | ✅ | `xcore/kernel/sandbox/ipc.py` |
| Event Bus (XBus) | ✅ | `xcore/kernel/events/bus.py` |
| Configuration centralisée | ✅ | `xcore/configurations/` |
| Permissions système | ✅ | `xcore/kernel/permissions/` |
| Hooks et Middleware | ✅ | `xcore/kernel/runtime/middlewares/` |
| Scanner de sécurité AST | ✅ | `xcore/kernel/security/validation.py` |

---

## ⚡ V2 — Industrialisation
**Objectif : Renforcer le runtime et préparer le distribué.**

| Fonctionnalité | État | Localisation / Note |
| :--- | :---: | :--- |
| ExecutionMode.EPHEMERAL | ✅ | `xcore/kernel/runtime/ephemeral_handler.py` |
| Warm Pool Plugins | ✅ | `xcore/kernel/runtime/warm_pool.py` |
| Schema Registry | ✅ | `xcore/kernel/schema/registry.py` |
| Validation automatique des contrats | ✅ | `xcore/kernel/schema/checker.py` |
| OpenTelemetry complet | ✅ | Vrai `TracerProvider` (console/OTLP-HTTP) — `xcore/kernel/observability/tracing.py` |
| Tracing distribué | ✅ | Propagation W3C traceparent HTTP + IPC sandbox — `http_middleware.py`, `sandbox/ipc.py` |
| Métriques Prometheus | ✅ | `xcore/kernel/observability/metrics.py` |
| Plugin Registry privé | ✅ | `xcore/registry/index.py` |
| Hot Cache avancé | ✅ | Backend étagé (mémoire L1 + Redis L2) — `xcore/services/cache/backends/tiered.py` |
| Optimisations loader | ✅ | Tri topologique par vagues implémenté |

**Fenêtre de maintenance V2** : V2 reste feature-complete et tourne en production jusqu'à **décembre 2026** avant le démarrage de V3 — chaque bug trouvé en prod est patché en release V2.3.x plutôt que fondu dans le travail V3. Voir `CHANGELOG.md`.

---

## 🌐 V3 — Distribution
**Objectif : Sortir du mono-processus.**

| Fonctionnalité | État | Localisation / Note |
| :--- | :---: | :--- |
| Federation statique | ❌ | Non implémenté |
| FederatedHandler | ❌ | Non implémenté |
| Routage inter-nœuds | ❌ | Non implémenté |
| Cluster IPC | ❌ | Non implémenté |
| Distributed Event Bus | ❌ | Non implémenté |
| Multi-tenancy complet | ✅ | `xcore/kernel/tenancy/` (Wrappers DB/Cache/Sched) |
| AgentBase IA | ❌ | Non implémenté |
| Hot Reload Plugins | ✅ | `PluginLoader.reload` fonctionnel |
| Service Hot-Swap | ✅ | Partiel via reload et Registry dynamique |
| Circuit Breaker | ❌ | Non implémenté |
| Failover | ❌ | Non implémenté |

---

## ☁️ V4 — Cloud Native Platform
**Objectif : Transformer XCore en plateforme.**

| Fonctionnalité | État | Localisation / Note |
| :--- | :---: | :--- |
| Marketplace publique | ⚠️ | Client de base présent (`xcore/marketplace/`) |
| Cluster Manager | ❌ | Prévu |
| Auto-scaling | ❌ | Prévu |
| Plugin Store | ❌ | Prévu |
| XCore Hub | ❌ | Prévu |

---

## 🤖 V5 — Intelligence Native
**Objectif : Faire de XCore une plateforme IA-native.**

| Fonctionnalité | État | Localisation / Note |
| :--- | :---: | :--- |
| XMind intégré au kernel | ❌ | Concept |
| Agents distribués | ❌ | Concept |
| MCP Native | ❌ | Concept |
| AI Service Discovery | ❌ | Concept |

---

## 🔍 Analyse Technique (MàJ v2.7.0)

### Points Forts
- **Runtime Avancé (V2)** : Le support des plugins éphémères avec Warm Pool est une réussite technique majeure, permettant des performances "cold start" minimales.
- **Sécurité & Performance** : Les optimisations récentes sur l'EventBus et le moteur de permissions ont réduit la latence sur le chemin critique.
- **Observabilité (V2)** : Vrai SDK OpenTelemetry + propagation W3C bout en bout (HTTP → appels plugins → IPC sandbox) — clôt les deux derniers ⚠️ de V2.
- **Tenancy (V3)** : L'isolation des ressources (DB/Cache) par tenant est mature et validée par les tests d'intégration.
- **Durcissement du cycle de vie des plugins (V2, v2.6.0)** : état actif/inactif persistant (`PluginStateStore`) qui survit aux redémarrages, ramasse-miette forcé au unload (jobs scheduler, health checks, abonnements events/hooks, services exportés — fuyaient silencieusement auparavant), et une surface de contrôle HTTP (`/plugins/ipc/registry|enable|disable|audit|events`) avec journal d'audit des appels IPC et de l'activité events/hooks. Voir `CHANGELOG.md` [2.6.0].
- **Hygiène des dépendances (v2.7.0)** : `dependencies` du noyau réduit à ce dont `import xcore` et le boot zero-config ont réellement besoin ; les paquets spécifiques à un backend (drivers DB, Redis, Celery, Alembic, exporteur OTLP) déplacés en extras optionnels — corrige au passage un trou où `prometheus-client` était importé par du code noyau mais uniquement disponible en dépendances dev. Voir `CHANGELOG.md` [2.7.0].

### Limites connues à suivre pendant la fenêtre de maintenance V2
- **`self.tracer` / `self.metrics` / `self.health` valent `None` dans les plugins ephemeral/sandboxed** — aucun `PluginContext` injecté dans `sandbox/worker.py`. Le tracing automatique côté superviseur couvre quand même ces appels ; seuls les spans/métriques custom écrits dans le code d'un plugin ephemeral sont affectés.
- **Le cache étagé n'a pas d'invalidation push inter-nœuds** — la fraîcheur du L1 est bornée par le `ttl`, pas garantie immédiate. Compromis assumé et documenté.
- **Évasion de sandbox confirmée par test dynamique (28/09/2026)** : 3 techniques fonctionnelles permettent à un plugin `sandboxed` d'exécuter des commandes arbitraires sur l'hôte — `asyncio.create_subprocess_exec`/`_shell` (module absent de toute liste noire), `().__class__.__bases__[0].__subclasses__()` remontant vers un `subprocess.Popen` déjà chargé (contourne à la fois le scan AST statique et le guard d'import runtime, puisqu'aucun `import` n'est jamais exécuté), et `import posix` dynamique (listé côté scanner statique mais absent du guard runtime — `posix` donne un accès quasi équivalent à `os`). Les limites mémoire (`RLIMIT_DATA`/`RLIMIT_RSS`) et le filesystem guard ont en revanche été vérifiés efficaces par les mêmes tests. Détail complet et pistes de correction dans `reports/sandbox_dynamic_security_analysis_2026-09-28.md` (rien d'appliqué pour l'instant — décision de portée en attente).
- **Pertinence de `ExecutionMode.LEGACY`** : c'est fonctionnellement un pur alias de `TRUSTED` (`PluginLoader` enregistre le même `TrustedActivator()` pour les deux), et pourtant c'est la **valeur par défaut** de `PluginManifest.execution_mode` quand un `plugin.yaml` omet le champ — un plugin non spécifié obtient donc silencieusement la confiance in-process complète plutôt que de retomber sur `sandboxed`, plus sûr par défaut. `LagacyActivator` (coquille dans le nom) existe mais est du code mort, levant `NotImplementedError` inconditionnellement. Recommandation : soit retirer `LEGACY` (renommer les références vers `TRUSTED`, supprimer l'activateur mort), soit le garder strictement comme alias historique documenté avec un avertissement au chargement incitant à choisir un mode explicite — mais le comportement actuel (défaut silencieux vers la confiance complète) mérite une décision délibérée, pas de rester tel quel sans examen.

### Chantiers Prioritaires (V3, une fois la fenêtre de maintenance terminée)
1. **Clustering (V3)** : C'est le saut technologique manquant. Le framework doit pouvoir communiquer entre nœuds (Cluster IPC).
2. **Résilience (V3)** : Implémenter Circuit Breaker et Failover pour la stabilité inter-plugins.
3. **Durcissement du sandbox (reporté de la maintenance V2)** : appliquer les correctifs de `reports/sandbox_dynamic_security_analysis_2026-09-28.md` — synchroniser les deux listes de modules interdits est trivial ; patcher directement `subprocess.Popen.__init__`/`os.fork`/`os.execve` (plutôt que de seulement filtrer les imports) est le correctif le plus robuste, qui résiste par construction aux futures variantes du même type de contournement.

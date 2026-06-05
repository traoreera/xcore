## Analyse du benchmark xcore v2.3.2

### Vue d'ensemble

Le benchmark tourne sur une machine 6 cœurs, 15.3GB RAM, CPU à ~878MHz (VM probablement throttlée), Python 3.12. Durée totale : **280s**, ce qui est long et reflète la complexité du boot/shutdown répété.

---

### Plugin Lifecycle

**Single load** : mean=3.7ms, p99=49ms — la variance est énorme (std=5.4ms, max=57ms). Le p99 à 49ms indique des pics de GC ou de contention sur le système de fichiers. Le code confirme le problème : `_do_load()` fait `del sys.modules[name]` puis un `spec_from_file_location` + `exec_module` à chaque itération. L'isolation via namespace (`xcore_plugin_{name}`) est correcte mais coûteuse.

**Single unload** : mean=0.35ms — rapide, cohérent. Le cleanup de `sys.modules` est bien délimité.

**Reload** : mean=0.9ms, p99=1.5ms, max=48ms — là encore un outlier inexpliqué. Le reload fait `_do_unload` + `_do_load` en séquence, le max à 48ms suggère une contention au moment du réimport.

**Batch load** : la tendance décroissante est bonne (30ms/plugin à 5, 11ms/plugin à 50), mais les `errors: -1` sont un signal rouge. En regardant le code de `bench_batch_load`, `errors = n - loaded` et `loaded = len(app.plugins.list_plugins())`. Le fait d'obtenir 101 plugins pour 100 demandés (`6/5 loaded`) indique que le plugin virtuel `xcore` (enregistré dans `KernelHandler`) est comptabilisé dans `list_plugins()` mais pas dans `n`. Ce n'est pas un vrai bug de perf mais un bug de mesure.

---

### Plugin Calls

**sequential_call_ping** : mean=1.15ms, **errors=1000** — toutes les requêtes sont en erreur. En regardant le code, `bench_sequential_calls` vérifie `r.get("status") != "ok"` mais le plugin `ping` retourne `{"status": "ok", "pong": True, ...}`. La cause probable est la vérification de permission : `PermissionMiddleware` appelle `engine.check(plugin_name, resource, action)` où `resource = kwargs.get("resource") or action`. Sans `grant_all`, le plugin n'a pas de policy chargée → DENY. Les mesures de latence restent valides (le pipeline s'exécute jusqu'au deny), mais le throughput affiché est trompeur.

**sequential_call_echo_payload** : mean=1.41ms, 0 erreurs — cohérent car ici les permissions sont apparemment accordées (ou le benchmark grant_all quelque part). La différence avec ping est suspecte et mérite investigation.

**Concurrent calls** : les erreurs 10/50/100 confirment le même problème de permission que ping. La latence moyenne ~1.4-2ms sous concurrence asyncio sur un seul plugin est raisonnable, le throughput décroît de 709 à 481 ops/s en montant de 10 à 100 concurrents, ce qui révèle une **contention sur le Lock asyncio** de l'IPCChannel ou sur la state machine.

**Routing** : mean=0.24ms, 0 erreurs — très bon. Le routing pur (lookup dict + dispatch) est O(1) et ne passe pas par la même couche de permission que les appels directs.

---

### Middleware

**Pipeline 0 middlewares** : mean=0.0034ms, 296k ops/s — excellent, la compilation de pipeline en closures imbriquées (`_compile_pipeline`) est efficace.

**Pipeline 4 middlewares** : mean=0.016ms, 61k ops/s — overhead de ~0.013ms par appel pour 4 noop middlewares. C'est **4x** le baseline, soit ~3.25µs par middleware. Acceptable mais à surveiller en production avec des middlewares réels (tracing, rate limit, permissions).

---

### Events

**EventBus sans handler** : mean=6.6µs, 151k ops/s — le coût de base du lookup dict vide + création d'un objet `Event` à chaque appel.

**1 handler** : mean=59µs, 17k ops/s — un saut de **9x** pour un seul handler. Le coût vient de `asyncio.gather` même pour un seul handler. En regardant le code, quand `gather=True` (défaut), on wrap systématiquement dans `asyncio.gather` même pour n=1, ce qui crée une task asyncio inutile.

**10 handlers** : mean=178µs, 5.6k ops/s — croissance quasi-linéaire, cohérent.

**Wildcard** : mean=68µs — légèrement plus lent qu'un handler exact (59µs), le surcoût vient du parcours de `_wildcard_patterns` avec regex match. La pré-compilation de la regex est bien faite, mais le scan O(N_wildcards) reste.

**HookManager 5 hooks** : mean=0.94ms, 1k ops/s — **16x** plus lent que l'EventBus avec 10 handlers pour seulement 5 hooks. La raison est dans `_execute_single_hook` : pour chaque hook synchrone, on appelle `asyncio.to_thread()` qui soumet vers le thread pool executor, ce qui est catastrophiquement coûteux pour des fonctions CPU-bound triviales. Le code benchmark enregistre des `@hm.on` avec des fonctions sync, et HookManager les dispatche via `asyncio.to_thread` systématiquement.

---

### Permissions

**Cold** : mean=3.8µs, 262k ops/s — le `engine._cache.clear()` forcé à chaque itération est artificiel mais mesure bien le coût réel de `PolicySet.evaluate()` avec glob matching.

**Cached** : mean=2.0µs, 502k ops/s — speedup de **1.9x seulement**. Le cache devrait être bien plus rapide. En regardant le code, `_cache` est un dict Python simple `(plugin, resource, action) → PolicyEffect`, le lookup devrait être sub-microseconde. Le surcoût restant vient de `_audit()` appelé même sur un cache hit, qui fait `self._audit_log.append(entry)` + `events.emit_sync(...)` à chaque check.

---

### Cache

**cache_get_hot** : mean=1.57µs, 636k ops/s — excellent pour un backend mémoire LRU.

**cache_set_single** : mean=3.8µs, 261k ops/s — plus lent que get à cause du calcul de `expires_at` et de l'éviction LRU.

**mset 100 keys** : mean=169µs soit ~1.7µs/clé — linéaire, correct.

**mget 100 keys** : mean=51µs soit ~0.5µs/clé — plus rapide que mset, cohérent.

---

### Tenancy

**Cache wrapper overhead** : set raw=2.5µs vs set wrapped=3.5µs (+40%), get raw=1.3µs vs get wrapped=4.5µs (+246%). Le get wrappé est **3.4x plus lent** que le raw. En regardant `TenantAwareCache.get()`, le problème est le try/except autour du `cache.get()` pour gérer la différence de signature (avec/sans `default`), plus l'appel à `_current_tenant_id.get()` (ContextVar lookup) et la concaténation de string pour le préfixage. Rien de grave en absolu (4.5µs), mais le surcoût relatif est élevé.

**IPC Auth** : http_direct=0.22ms vs caller_allowed=2.15ms vs caller_denied=0.94ms. Le fast-path HTTP (caller=None) est 10x plus rapide que le path IPC. La différence entre allowed (2.15ms) et denied (0.94ms) est surprenante — le path denied devrait être plus rapide car il court-circuite avant d'appeler `next_call`. L'explication est que `next_fn = AsyncMock(return_value={"status": "ok"})` — le mock asyncio sur le path allowed ajoute un overhead non négligeable. Ces chiffres ne reflètent donc pas la réalité production.

**ipc_enforce_off_bypass** : mean=1.37ms alors qu'on s'attendrait à être proche du http_direct (0.22ms). Le bypass `enforce=False` appelle quand même `next_call` qui est un AsyncMock lent.

**wrap_services_per_call** : mean=7.9µs mais median=4.9µs — forte variance. Appeler `wrap_services_for_tenant()` à chaque requête crée de nouveaux objets wrapper à chaque fois. En production, ces wrappers sont créés au `_do_load()` du plugin (une seule fois), pas à chaque dispatch — le benchmark mesure donc un scénario qui n'existe pas vraiment.

---

### Capacity

La progression est erratique : 100 plugins en 4.7s (46ms/plugin), 500 plugins en **3.9s** (7.7ms/plugin), 1000 plugins en 29.8s (29.7ms/plugin). Le creux à 500 est suspect et probablement un artefact du GC ou du cache filesystem. `concurrent_calls_ok=0` pour tous les niveaux confirme le bug de permission identifié plus haut. La mémoire par plugin est quasi nulle (0.014MB à 100, ~0 ensuite) car le module Python est partagé — les plugins benchmarkés sont tous identiques et Python cache les bytecodes.

---

### Problèmes prioritaires à corriger

**Bug critique (permissions)** : `sequential_call_ping` et tous les concurrent calls ont 100% d'erreurs. Dans `PluginSupervisor.boot()`, `_load_permissions` est appelé via l'event `plugin.*.services_registered`, mais ce handler est réactif et peut arriver après les appels dans le benchmark. Il faudrait s'assurer que `_load_permissions` est appelé de manière synchrone après `load_all()`.

**HookManager via asyncio.to_thread** : remplacer l'appel systématique à `asyncio.to_thread` pour les fonctions sync triviales par un appel direct, et réserver `asyncio.to_thread` aux fonctions explicitement marquées comme bloquantes.

**EventBus single handler** : ajouter un fast-path qui évite `asyncio.gather` quand il n'y a qu'un seul handler.

**Audit sur cache hit des permissions** : déplacer l'audit après la vérification du cache, ou ne logger qu'en mode debug.

**TenantAwareCache.get** : simplifier la signature (choisir l'une des deux interfaces), éliminer le try/except chaud.

**Mesure batch load** : corriger le calcul d'erreurs en excluant le plugin virtuel `xcore` du compte.

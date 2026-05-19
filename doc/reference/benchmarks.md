# Performance & Benchmarks

Résultats mesurés sur Python 3.12.13 · Linux x86_64 · 8 CPUs · 15.3 GB RAM
Génération : 2026-05-14 (XCore v2.3.0) · `time.perf_counter` + pytest-benchmark

Reproduire les mesures :

> **Note** : Les benchmarks nécessitent l'installation du groupe `dev` (`poetry install` ou `uv sync`). Le package `psutil` est requis pour les métriques mémoire.

```bash
# Suite complète (script autonome — toutes catégories)
python scripts/benchmarks.py --output bench_results.json

# Suite ciblée
python scripts/benchmarks.py --suite tenancy permissions cache

# Benchmarks pytest (avec --benchmark-json pour CI)
.venv/bin/pytest tests/benchmarks/test_kernel_benchmarks.py \
                 tests/benchmarks/test_permission_bench.py \
                 tests/benchmarks/test_tenancy_bench.py \
                 --benchmark-only --benchmark-json=bench_results.json

# Benchmarks cache (script autonome)
python tests/benchmarks/cache_batch_perf.py
```

---

## 1. Permission Engine

### 1.1 Policy Matching (µs par opération)

La méthode `Policy.matches()` est le cœur du moteur de permissions. Elle compare une ressource et une action à un pattern glob.

| Test | Min (µs) | Moy (µs) | Ops/s |
|:-----|--------:|--------:|------:|
| `failure_action` — action non autorisée | **0.245** | 0.409 | **2 443 000** |
| `failure_resource` — ressource hors scope | 0.752 | 1.042 | 960 000 |
| `success` — match complet | 0.997 | 1.637 | 611 000 |

```
Policy.matches() — distribution des moyennes (µs)
─────────────────────────────────────────────────
 failure_action   ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░  0.41 µs
failure_resource   ▓▓▓▓▓▓▓▓▒░░░░░░░░░░░░░░░░░░░  1.04 µs
         success   ▓▓▓▓▓▓▓▓▓▓▓▓▒░░░░░░░░░░░░░░░  1.64 µs
                  0        0.5       1.0       1.5    2.0
```

> **Lecture** : Le short-circuit sur l'action (`failure_action`) est **4× plus rapide** qu'un match complet car la comparaison des actions se fait avant le glob de ressource.

### 1.2 Permission Engine — cache vs sans cache

Le `PermissionEngine` évalue un jeu de 6 paires `(resource, action)` contre 5 policies.

| Mode | Min (µs) | Moy (µs) | Ops/s |
|:-----|--------:|--------:|------:|
| Avec cache LRU | **85.5** | 113.1 | 8 843 |
| Sans cache (worst case) | 107.6 | 151.8 | 6 589 |

```
PermissionEngine — latence moyenne (µs)
────────────────────────────────────────
  avec cache   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░  113 µs
  sans cache   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░  152 µs
              0        50       100       150
```

**Gain du cache : ~25 % de latence en moins, +34 % de débit.**

---

## 2. Cache Service — Batch vs Séquentiel

### 2.1 MemoryBackend (100 clés, in-process)

| Opération | Séquentiel | Batch (mset/mget) | Gain |
|:----------|----------:|------------------:|-----:|
| SET × 100 | 0.28 ms | **0.14 ms** | 2× |
| GET × 100 | 0.09 ms | **0.07 ms** | 1.3× |

```
MemoryBackend — SET 100 clés (ms)
───────────────────────────────────
 Séquentiel   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░  0.28 ms
  Batch mset  ▓▓▓▓▓▓▒░░░░░░░░░  0.14 ms
             0      0.1     0.2     0.3
```

### 2.2 RedisCacheBackend (100 clés, 2 ms de latence réseau simulée)

| Opération | Séquentiel | Batch optimisé | Gain |
|:----------|----------:|--------------:|-----:|
| SET × 100 | 232.6 ms | **5.3 ms** | **44×** |
| GET × 100 | 227.1 ms | **2.9 ms** | **77×** |

```
Redis SET 100 clés — impact du batch (ms, 2 ms latence réseau)
──────────────────────────────────────────────────────────────
 Séquentiel   ████████████████████████████████████████  232 ms
 Pipeline     ▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   5.3 ms
             0               100              200      232
```

```
Redis GET 100 clés
────────────────────
 Séquentiel  ████████████████████████████████████████  227 ms
 MGET natif  ▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   2.9 ms
```

> **En production**, avec un Redis distant, toujours utiliser `mset`/`mget` pour les opérations par lot. Le gain est de 44–77× par rapport aux appels séquentiels.

---

## 3. Tenancy — TenantAwareCache et IPCAuthMiddleware

Mesures sur 10 000 itérations par benchmark.

### 3.1 TenantAwareCache — overhead du préfixage

| Benchmark | Mean (µs) | Median (µs) | P99 (µs) | Ops/s |
|:----------|----------:|------------:|---------:|------:|
| `cache_set_raw` — backend direct | **2.00** | 2.0 | 3.0 | 499 033 |
| `cache_set_wrapped` — TenantAwareCache | **2.81** | 2.7 | 5.0 | 355 271 |
| `cache_get_raw` — backend direct | **1.15** | 1.1 | 2.0 | 870 388 |
| `cache_get_wrapped` — TenantAwareCache | **3.41** | 2.9 | 6.0 | 292 958 |
| `cache_two_tenants_interleaved` — 2 tenants | **5.52** | 4.2 | 9.0 | 181 200 |

```
Overhead TenantAwareCache vs backend direct
───────────────────────────────────────────
    SET raw     ▓▓▓▓▓▓▒░░░░░░░░░░░  2.0 µs
    SET wrapped ▓▓▓▓▓▓▓▓▓░░░░░░░░░  2.8 µs  (+0.8 µs)
    GET raw     ▓▓▓▓░░░░░░░░░░░░░░  1.15 µs
    GET wrapped ▓▓▓▓▓▓▓▓▓▓▓▒░░░░░░  3.4 µs  (+2.2 µs)
               0        2        4        6   µs
```

> L'overhead de préfixage est de **0.8 µs** sur set et **2.2 µs** sur get — négligeable face à la latence réseau Redis (≥ 1 ms).

### 3.2 IPCAuthMiddleware — latence par scénario

| Scénario | Mean (µs) | Median (µs) | P99 (µs) | Ops/s |
|:---------|----------:|------------:|---------:|------:|
| HTTP direct (`caller=None`) — fast path | **270** | 151 | 970 | 3 707 |
| IPC autorisé (`caller` dans la liste) | **318** | 184 | 1 075 | 3 142 |
| IPC refusé (deny-by-default) | **331** | 284 | 1 069 | 3 026 |
| `enforce_ipc=False` — bypass complet | **301** | 190 | 1 257 | 3 323 |

> La latence moyenne (~300 µs) est dominée par le coût d'appel de `AsyncMock` — en production, le vrai handler est bien plus léger. L'overhead **propre au middleware** (`allowed_callers` lookup) est **< 1 µs**.

### 3.3 wrap_services_for_tenant() — coût d'instanciation

| Benchmark | Mean (µs) | Ops/s |
|:----------|----------:|------:|
| `wrap_services_per_call` (cache seul) | **1.59** | 630 008 |

> Créer les wrappers tenant-aware coûte **~1.6 µs** par appel plugin. Ce coût est payé une fois par dispatch, avant l'exécution du handler.

---

## 4. Synthèse Comparative

```
Composant                          Débit (ops/s)    Latence moy
──────────────────────────────────────────────────────────────────
Policy.matches (match)             611 000          1.6 µs
Policy.matches (miss action)       2 443 000        0.4 µs
PermissionEngine (6 checks, cold)  424 174          2.36 µs
PermissionEngine (6 checks, LRU)   371 353          2.69 µs
Cache MemoryBackend SET            374 751          2.7 µs
Cache MemoryBackend GET (hot)      837 358          1.2 µs
Cache MemoryBackend MSET 100 keys  8 969            111 µs
Cache MemoryBackend MGET 100 keys  23 731           42 µs
Cache Redis MSET 100 keys          ~18 900          5.3 ms (2ms net)
Cache Redis sequential SET         ~430             232 ms (2ms net)
TenantAwareCache SET               355 271          2.8 µs
TenantAwareCache GET               292 958          3.4 µs
wrap_services_for_tenant()         630 008          1.6 µs
IPCAuthMiddleware (allow)          3 142            318 µs*
IPCAuthMiddleware (deny)           3 026            331 µs*
```

*\* Mesuré avec AsyncMock ; overhead propre au middleware < 1 µs.*

---

## 5. Évolution des Performances (v2.x)

| Version | Changement | Impact |
|:--------|:-----------|:-------|
| **v2.3.0** | `TenantAwareCache` — préfixage tenant | +0.8 µs/SET, +2.2 µs/GET |
| **v2.3.0** | `IPCAuthMiddleware` — lookup allowed_callers | < 1 µs overhead propre |
| **v2.3.0** | `wrap_services_for_tenant()` — instanciation wrappers | 1.6 µs/appel |
| **v2.1.2** | Cache LRU sur `PermissionEngine` | +34 % débit engine |
| **v2.1.2** | `mset`/`mget` natif sur Redis backend | 44–77× batch throughput |
| **v2.0.0** | Moteur de policies (fnmatch + eval order) | Baseline |

---

## 6. Interprétation et Recommandations

### Permission Engine
- Le cache LRU est activé par défaut. Ne pas l'invalider entre chaque requête sans raison.
- Un plugin avec 5 policies évalue une paire `(resource, action)` en **~2.4 µs**.
- Le budget total par requête HTTP est largement inférieur à la milliseconde pour la couche permissions.

### Cache Service
- Toujours préférer les APIs batch (`mset`, `mget`) dès que `n > 5` clés.
- Avec Redis en production (réseau ≥ 1 ms), le gain batch est **toujours supérieur à 20×**.
- Pour des lectures à très haute fréquence, envisager `MemoryBackend` comme L1 devant Redis (L2).

### Tenancy
- L'overhead de `TenantAwareCache` est **< 3 µs** par opération — négligeable en production avec Redis.
- `wrap_services_for_tenant()` coûte **1.6 µs** par appel plugin : activez sans hésitation même à fort trafic.
- `IPCAuthMiddleware` : l'overhead propre du middleware est **< 1 µs** ; le reste est le coût du handler lui-même.

---

## Liens Connexes

- [Service Cache — Guide](../guides/services.md)
- [Security & Permissions](../guides/security.md)
- [Testing Guide](../development/testing.md)

# Performance & Benchmarks

Résultats mesurés sur Python 3.14 · pytest-benchmark 5.2.3 · `time.perf_counter`
Machine : Linux x86_64, génération 2026-04-29 (XCore v2.1.2)

Reproduire les mesures :

```bash
# Benchmarks kernel (pytest-benchmark)
poetry run pytest tests/benchmarks/test_kernel_benchmarks.py \
                  tests/benchmarks/test_permission_bench.py \
                  --benchmark-only --benchmark-json=bench_results.json

# Benchmarks cache (script autonome)
poetry run python tests/benchmarks/cache_batch_perf.py
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

## 3. Synthèse Comparative

```
Composant                Débit (ops/s)          Latence moy
─────────────────────────────────────────────────────────────
Policy.matches (match)   611 000 ops/s          1.6 µs
Policy.matches (miss)    2 443 000 ops/s        0.4 µs
PermissionEngine+cache   8 843 ops/s            113 µs   ← 6 checks/eval
PermissionEngine raw     6 589 ops/s            152 µs
Cache Memory MSET        ~700 000 ops/s         0.14 ms (100 keys)
Cache Redis MSET         ~18 900 ops/s          5.3 ms  (100 keys, 2ms net)
Cache Redis sequential   ~430 ops/s             232 ms  (100 keys, 2ms net)
```

---

## 4. Évolution des Performances (v2.x)

| Version | Changement | Impact |
|:--------|:-----------|:-------|
| **v2.1.2** | Cache LRU sur `PermissionEngine` | +34 % débit engine |
| **v2.1.2** | `mset`/`mget` natif sur Redis backend | 44–77× batch throughput |
| **v2.0.0** | Moteur de policies (fnmatch + eval order) | Baseline |

---

## 5. Interprétation et Recommandations

### Permission Engine
- Le cache LRU est activé par défaut. Ne pas l'invalider entre chaque requête sans raison.
- Un plugin avec 5 policies évalue une paire `(resource, action)` en **~85–150 µs** cache compris.
- Le budget total par requête HTTP est largement inférieur à la milliseconde pour la couche permissions.

### Cache Service
- Toujours préférer les APIs batch (`mset`, `mget`) dès que `n > 5` clés.
- Avec Redis en production (réseau ≥ 1 ms), le gain batch est **toujours supérieur à 20×**.
- Pour des lectures à très haute fréquence, envisager `MemoryBackend` comme L1 devant Redis (L2).

---

## Liens Connexes

- [Service Cache — Guide](../guides/services.md)
- [Security & Permissions](../guides/security.md)
- [Testing Guide](../development/testing.md)

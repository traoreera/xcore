# Plan de travail xcore — vers Production-Ready

---

## Phase 1 — Stabilisation (2-3 semaines)
*Objectif : zéro bug connu, base solide*

**Semaine 1 — Corriger les bugs identifiés**

Priorité absolue, dans cet ordre :

```
1. ipc.py          → UnboundLocalError sur timeout (variable e hors scope)
2. supervisor.py   → _handle_crash() récursif → RecursionError
3. runner.py       → mems() ne met pas à jour les services existants au reload
5. plugin_manifest → _inject_envfile avec dict vide
```

**Semaine 2 — Tests unitaires core**

Les tests qu'on a écrits couvrent les contrats plugin mais pas le core lui-même. Il faut tester :

```
- _topo_sort()          → cycles, deps manquantes, ordre stable
- load_manifest()       → requires lu, env variables, modes
- mems()                → propagation après on_load, après reload
- _flush_services()     → ordre des vagues
- RateLimiter           → fenêtre glissante sous charge
- IPCChannel            → timeout, EOF, JSON invalide
```

**Semaine 3 — CI fonctionnel**

Brancher les workflows GitHub Actions qu'on a générés :
```
- ci.yml      → lint + typecheck + tests sur chaque push
- pr.yml      → gate sur chaque PR
- security.yml → audit hebdomadaire
```

---

## Phase 2 — Observabilité (2-3 semaines)
*Objectif : savoir ce qui se passe en prod*

**Logs structurés**

Remplacer tous les `logger.info(f"...")` par des logs JSON structurés :

```python
# Avant
logger.info(f"[{manifest.name}] ✅ TRUSTED | timeout={...}s")

# Après
logger.info("plugin.loaded", extra={
    "plugin": manifest.name,
    "mode": "trusted",
    "timeout": manifest.resources.timeout_seconds,
    "duration_ms": round((time.monotonic() - t0) * 1000),
})
```

**Métriques**

Ajouter un endpoint `/metrics` compatible Prometheus :

```
xcore_plugin_load_total{plugin, mode, status}
xcore_plugin_call_duration_seconds{plugin, action}
xcore_plugin_call_errors_total{plugin, action, code}
xcore_sandbox_restarts_total{plugin}
xcore_rate_limit_exceeded_total{plugin}
```

**Health check global**

```
GET /health
→ {
    "status": "ok" | "degraded" | "down",
    "plugins": {
      "erp_core":  {"status": "ok",   "uptime": 3600},
      "erp_auth":  {"status": "ok",   "uptime": 3598},
      "erp_crm":   {"status": "degraded", "restarts": 2}
    }
  }
```

**Connecter Snapshot au watcher**

```python
# Dans PluginManager — watcher automatique en dev
async def _watch_plugins(self):
    snapshot = Snapshot()
    while True:
        diff = snapshot(self.plugins_dir)
        if diff["modified"]:
            for path in diff["modified"]:
                plugin_name = Path(path).parts[0]
                await self.reload(plugin_name)
        await asyncio.sleep(2)
```

---

## Phase 3 — Sécurité (3-4 semaines)
*Objectif : résistant aux plugins malveillants*

**Semaine 1 — Hardening sandbox**

```python
# worker.py — bloquer les binaires système
env = {
    "PATH": "/usr/bin/python3",  # pas de curl, wget, nc
    "HOME": str(sandbox_home),
    # Pas d'héritage de l'env uvicorn
}

# Ajouter seccomp si Linux (bloque les syscalls dangereux)
# → pas de fork(), pas de socket(), pas d'exec()
```

**Semaine 2 — Scanner AST renforcé**

```python
# scanner.py — ajouter importlib aux interdits pour Sandboxed
DEFAULT_FORBIDDEN_MODULES.add("importlib")

# Bloquer les accès dunder via getattr même dans les strings
# Détecter les __subclasses__() et __globals__ utilisés pour escape
```

**Semaine 3 — Audit signer.py**

```python
# Empêcher un plugin de se re-signer lui-même
# La clé secrète ne doit jamais être dans self._services
# Ajouter une liste blanche des plugins autorisés à signer
```

**Semaine 4 — Rate limiting par IP + par tenant**

```python
# Aujourd'hui : rate limit par plugin uniquement
# Ajouter : rate limit par (plugin + tenant_id)
self._rate.check(plugin_name, tenant_id=request.headers.get("X-Tenant-ID"))
```

---

## Phase 4 — Robustesse (2-3 semaines)
*Objectif : tient sous charge, se rétablit seul*

**Circuit breaker sur les plugins**

```python
# Si un plugin échoue 5 fois en 60s → circuit ouvert
# Réessai automatique après 30s (half-open)
# Évite de marteau les plugins en état FAILED
```

**Rollback au reload**

```python
# Avant reload → snapshot de l'état
# Si reload échoue → restaurer l'ancienne version
async def reload(self, plugin_name):
    backup = self._snapshot_plugin(plugin_name)
    try:
        await self._do_reload(plugin_name)
    except Exception:
        await self._restore(backup)
        raise
```

**Graceful degradation**

```python
# Si erp_auth est down → les routes qui ne nécessitent pas d'auth
# continuent de fonctionner au lieu de tout faire tomber
```

---

## Phase 5 — Multi-tenant (3-4 semaines)
*Seulement si SaaS exposé nécessaire*

```
- Isolation des services par tenant (DB séparées ou schemas séparés)
- Rate limiting par tenant
- Audit log par tenant (qui a appelé quoi, quand)
- Plugin whitelisting par tenant (tenant A n'a pas accès aux plugins de tenant B)
```

---

## Récapitulatif

| Phase | Durée | Résultat |
|-------|-------|---------|
| 1 — Stabilisation | 2-3 semaines | Zéro bug connu, CI actif |
| 2 — Observabilité | 2-3 semaines | Tu vois ce qui se passe |
| 3 — Sécurité | 3-4 semaines | Résistant aux plugins malveillants |
| 4 — Robustesse | 2-3 semaines | Tient sous charge |
| 5 — Multi-tenant | 3-4 semaines | SaaS exposé possible |

**Total : 3-4 mois** pour passer de MVP interne solide à SaaS production-ready.

---

## Conseil concret

Ne saute pas les phases. La tentation va être de passer directement à la Phase 5 (multi-tenant) parce que c'est la plus visible. Mais sans la Phase 1 et 2, tu vas déboguer en aveugle sous charge et tout te coûtera 3x plus de temps.

**Commence lundi par `ipc.py` — c'est 5 lignes et c'est le bug le plus dangereux en prod.**
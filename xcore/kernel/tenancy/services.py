"""
tenancy/services.py — Wrappers tenant-aware pour DB, Cache et Scheduler.

Le plugin écrit :
    cache.get("invoices")
    db.execute("SELECT * FROM orders")
    scheduler.add_job(fn, job_id="cleanup")

xcore préfixe automatiquement avec tenant_id :
    cache     → clé  "acme:invoices"
    db        → SET search_path=acme avant chaque requête (PostgreSQL)
    scheduler → job_id "acme:cleanup"

Le tenant_id courant est résolu depuis un ContextVar asyncio — chaque tâche
(chaque requête HTTP) dispose de sa propre valeur, sans mutation d'état partagé.
"""

from __future__ import annotations

import contextlib
import re
from contextvars import ContextVar
from typing import Any

# Tenant actif pour la tâche asyncio courante.
# Initialisé à "default". Mis à jour par supervisor._dispatch à chaque requête.
_current_tenant_id: ContextVar[str] = ContextVar("xcore_tenant_id", default="default")

# Tenant ID valide : lettres, chiffres, tirets, underscores uniquement.
_VALID_TENANT = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_tenant(tenant_id: str) -> str:
    if not _VALID_TENANT.match(tenant_id):
        raise ValueError(
            f"tenant_id invalide : {tenant_id!r} "
            "(caractères autorisés : a-z A-Z 0-9 _ -)"
        )
    return tenant_id


class TenantAwareCache:
    """
    Wrapper sur le cache qui préfixe toutes les clés avec le tenant courant.

    tenant_id optionnel :
      - fourni → tenant statique (utile pour les tests)
      - absent  → tenant lu depuis _current_tenant_id (ContextVar) à chaque opération
    """

    def __init__(self, cache: Any, tenant_id: str | None = None) -> None:
        self._cache = cache
        self._static_tenant = tenant_id

    @property
    def _tenant(self) -> str:
        return (
            self._static_tenant
            if self._static_tenant is not None
            else _current_tenant_id.get()
        )

    def _k(self, key: str) -> str:
        return f"{self._tenant}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        # On ne passe pas default au backend car tous ne le supportent pas (TypeError).
        # On gère le fallback ici : si None, on retourne default.
        result = await self._cache.get(self._k(key))
        return result if result is not None else default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._cache.set(self._k(key), value, ttl=ttl)

    async def delete(self, key: str) -> None:
        await self._cache.delete(self._k(key))

    async def exists(self, key: str) -> bool:
        return await self._cache.exists(self._k(key))

    async def incr(self, key: str, delta: int = 1) -> int:
        return await self._cache.incr(self._k(key), delta)

    async def keys(self, pattern: str = "*") -> list[str]:
        raw = await self._cache.keys(f"{self._tenant}:{pattern}")
        prefix = f"{self._tenant}:"
        return [k[len(prefix) :] if k.startswith(prefix) else k for k in raw]

    async def clear(self, pattern: str = "*") -> int:
        matched = await self._cache.keys(f"{self._tenant}:{pattern}")
        for k in matched:
            await self._cache.delete(k)
        return len(matched)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cache, name)


class TenantAwareDB:
    """
    Wrapper sur la DB qui isole par tenant via search_path PostgreSQL.

    tenant_id optionnel :
      - fourni → tenant statique
      - absent  → tenant lu depuis _current_tenant_id (ContextVar)
    SET search_path utilise un identifiant validé pour éviter toute injection SQL.
    Pour MySQL ou SQLite, le SET search_path est ignoré silencieusement.
    """

    def __init__(self, db: Any, tenant_id: str | None = None) -> None:
        self._db = db
        self._static_tenant = tenant_id

    @property
    def _tenant(self) -> str:
        return (
            self._static_tenant
            if self._static_tenant is not None
            else _current_tenant_id.get()
        )

    async def _set_tenant_schema(self, conn: Any) -> None:
        try:
            tenant = _validate_tenant(self._tenant)
            await conn.execute(f"SET search_path TO {tenant}, public")
        except ValueError:
            raise
        except Exception:
            pass

    @contextlib.asynccontextmanager
    async def session(self):
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            yield sess

    async def execute(self, query: str, *args, **kwargs) -> Any:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            return await sess.execute(query, *args, **kwargs)

    async def fetch_one(self, query: str, *args, **kwargs) -> Any:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            return await sess.fetch_one(query, *args, **kwargs)

    async def fetch_all(self, query: str, *args, **kwargs) -> list:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            return await sess.fetch_all(query, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._db, name)


class TenantAwareScheduler:
    """
    Wrapper sur le scheduler qui préfixe les job_id avec le tenant courant.

    scheduler.add_job(fn, job_id="cleanup") → job_id "acme:cleanup"
    scheduler.remove_job("cleanup")         → retire "acme:cleanup"

    tenant_id optionnel :
      - fourni → tenant statique
      - absent  → tenant lu depuis _current_tenant_id (ContextVar)
    """

    def __init__(self, scheduler: Any, tenant_id: str | None = None) -> None:
        self._scheduler = scheduler
        self._static_tenant = tenant_id

    @property
    def _tenant(self) -> str:
        return (
            self._static_tenant
            if self._static_tenant is not None
            else _current_tenant_id.get()
        )

    def _jid(self, job_id: str) -> str:
        return f"{self._tenant}:{job_id}"

    def add_job(
        self,
        func: Any,
        *args,
        id: str | None = None,
        job_id: str | None = None,
        **kwargs,
    ) -> Any:
        raw_id = id or job_id
        if raw_id is not None:
            kwargs["job_id"] = self._jid(raw_id)
        return self._scheduler.add_job(func, *args, **kwargs)

    def remove_job(self, job_id: str) -> None:
        self._scheduler.remove_job(self._jid(job_id))

    def get_job(self, job_id: str) -> Any:
        return self._scheduler.get_job(self._jid(job_id))

    def pause_job(self, job_id: str) -> None:
        self._scheduler.pause_job(self._jid(job_id))

    def resume_job(self, job_id: str) -> None:
        self._scheduler.resume_job(self._jid(job_id))

    def get_jobs(self) -> list:
        """Jobs filtrés pour le tenant courant — objets APScheduler (attribut .id)."""
        prefix = f"{self._tenant}:"
        return [
            j
            for j in self._scheduler.get_jobs()
            if getattr(j, "id", "").startswith(prefix)
        ]

    def jobs(self) -> list:
        """Jobs filtrés pour le tenant courant — dicts SchedulerService (clé 'id')."""
        prefix = f"{self._tenant}:"
        return [j for j in self._scheduler.jobs() if j.get("id", "").startswith(prefix)]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._scheduler, name)


def wrap_services_for_tenant(
    services: dict[str, Any],
    tenant_id: str | None = None,
    isolate_cache: bool = True,
    isolate_db: bool = True,
    isolate_scheduler: bool = False,
) -> dict[str, Any]:
    """
    Retourne une copie des services avec wrappers tenant-aware.

    tenant_id optionnel :
      - fourni → tenant statique dans les wrappers (tests, wrapping explicite)
      - absent  → les wrappers lisent le tenant depuis _current_tenant_id (ContextVar)
                  safe pour la concurrence, aucune mutation à chaque requête
    """
    wrapped = dict(services)

    if isolate_cache and wrapped.get("cache") is not None:
        wrapped["cache"] = TenantAwareCache(wrapped["cache"], tenant_id)

    if isolate_db:
        if wrapped.get("db") is not None:
            wrapped["db"] = TenantAwareDB(wrapped["db"], tenant_id)
        for key, svc in list(wrapped.items()):
            if key in ("db", "cache", "scheduler", "worker") or key.startswith("ext."):
                continue
            if _is_db_adapter(svc):
                wrapped[key] = TenantAwareDB(svc, tenant_id)

    if isolate_scheduler and wrapped.get("scheduler") is not None:
        wrapped["scheduler"] = TenantAwareScheduler(wrapped["scheduler"], tenant_id)

    return wrapped


def _is_db_adapter(svc: Any) -> bool:
    cls_name = type(svc).__name__
    return any(
        cls_name.endswith(suffix)
        for suffix in ("SQLAdapter", "AsyncSQLAdapter", "MongoDBAdapter", "DBAdapter")
    )

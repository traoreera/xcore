"""
tenancy/services.py — Wrappers tenant-aware pour DB, Cache et Scheduler.

Le plugin écrit :
    cache.get("invoices")
    db.execute("SELECT * FROM orders")
    scheduler.add_job(fn, id="cleanup")

xcore préfixe automatiquement avec tenant_id :
    cache     → clé  "acme:invoices"
    db        → SET search_path=acme avant chaque requête (PostgreSQL)
    scheduler → job_id "acme:cleanup"

Le plugin ne gère jamais le tenant — c'est transparent.
"""

from __future__ import annotations

import contextlib
from typing import Any


class TenantAwareCache:
    """
    Wrapper sur le cache qui préfixe toutes les clés avec tenant_id.

    Délègue toutes les opérations au cache sous-jacent après avoir
    préfixé la clé : "<tenant_id>:<key>".
    """

    def __init__(self, cache: Any, tenant_id: str) -> None:
        self._cache = cache
        self._tenant = tenant_id

    def _k(self, key: str) -> str:
        return f"{self._tenant}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        try:
            result = await self._cache.get(self._k(key), default)
        except TypeError:
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
        """Supprime les clés du tenant courant correspondant au pattern."""
        matched = await self._cache.keys(f"{self._tenant}:{pattern}")
        for k in matched:
            await self._cache.delete(k)
        return len(matched)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cache, name)


class TenantAwareDB:
    """
    Wrapper sur la DB qui isole par tenant via search_path PostgreSQL.

    Avant chaque requête SQL, exécute :
        SET search_path TO <tenant_id>, public

    Ce qui redirige toutes les tables vers le schéma du tenant.
    Pour MySQL ou SQLite, silencieux (pas de search_path).
    """

    def __init__(self, db: Any, tenant_id: str) -> None:
        self._db = db
        self._tenant = tenant_id

    async def _set_tenant_schema(self, conn: Any) -> None:
        try:
            await conn.execute(f"SET search_path TO {self._tenant}, public")
        except Exception:
            pass

    @contextlib.asynccontextmanager
    async def session(self):
        """Retourne une session avec search_path configuré."""
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
    Wrapper sur le scheduler qui préfixe les job_id avec tenant_id.

    scheduler.add_job(fn, id="cleanup") → job_id "acme:cleanup"
    scheduler.remove_job("cleanup")     → retire "acme:cleanup"
    scheduler.get_job("cleanup")        → cherche "acme:cleanup"
    """

    def __init__(self, scheduler: Any, tenant_id: str) -> None:
        self._scheduler = scheduler
        self._tenant = tenant_id

    def _jid(self, job_id: str) -> str:
        return f"{self._tenant}:{job_id}"

    def add_job(self, func: Any, *args, id: str | None = None, **kwargs) -> Any:
        if id is not None:
            kwargs["id"] = self._jid(id)
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
        """Retourne uniquement les jobs du tenant courant."""
        prefix = f"{self._tenant}:"
        return [
            j
            for j in self._scheduler.get_jobs()
            if getattr(j, "id", "").startswith(prefix)
        ]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._scheduler, name)


def wrap_services_for_tenant(
    services: dict[str, Any],
    tenant_id: str,
    isolate_cache: bool = True,
    isolate_db: bool = True,
    isolate_scheduler: bool = False,
) -> dict[str, Any]:
    """
    Retourne une vue des services avec les wrappers tenant-aware.

    - Wrappe tous les adapters DB (clé "db" + tout adapter de type AsyncSQLAdapter)
    - Wrappe le cache (clé "cache")
    - Wrappe le scheduler si isolate_scheduler=True (clé "scheduler")

    Les flags viennent de TenancyConfig.
    """
    wrapped = dict(services)

    if isolate_cache and wrapped.get("cache") is not None:
        wrapped["cache"] = TenantAwareCache(wrapped["cache"], tenant_id)

    if isolate_db:
        # Wrappe la clé principale "db"
        if wrapped.get("db") is not None:
            wrapped["db"] = TenantAwareDB(wrapped["db"], tenant_id)

        # Wrappe tous les autres adapters SQL nommés (enregistrés par DatabaseManager)
        for key, svc in list(wrapped.items()):
            if key in ("db", "cache", "scheduler", "worker") or key.startswith("ext."):
                continue
            if _is_db_adapter(svc):
                wrapped[key] = TenantAwareDB(svc, tenant_id)

    if isolate_scheduler and wrapped.get("scheduler") is not None:
        wrapped["scheduler"] = TenantAwareScheduler(wrapped["scheduler"], tenant_id)

    return wrapped


def _is_db_adapter(svc: Any) -> bool:
    """Détecte si un service est un adapter de base de données."""
    cls_name = type(svc).__name__
    return any(
        cls_name.endswith(suffix)
        for suffix in ("SQLAdapter", "AsyncSQLAdapter", "MongoDBAdapter", "DBAdapter")
    )

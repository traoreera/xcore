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
import functools
import inspect
import re
from contextvars import ContextVar
from typing import Any

from ..observability import get_logger

logger = get_logger("xcore.tenancy.services")

# Tenant actif pour la tâche asyncio courante.
# Initialisé à "default". Mis à jour par supervisor._dispatch à chaque requête.
_current_tenant_id: ContextVar[str] = ContextVar("xcore_tenant_id", default="default")

# Tenant ID valide : lettres, chiffres, tirets, underscores uniquement, 63 octets
# max (limite des identifiants PostgreSQL, au-delà ils sont tronqués en silence
# et deux tenants distincts pourraient partager un schéma). `fullmatch` : `$`
# accepterait un retour à la ligne final.
_VALID_TENANT = re.compile(r"[a-zA-Z0-9_-]{1,63}")

# Le tenant vient d'un en-tête HTTP non authentifié : il est donc validé à
# chaque usage (DB, cache, scheduler), jamais seulement à l'entrée. Sans cela,
# un tenant "*" servirait de glob dans `cache.keys()/clear()` et viderait les
# clés de tous les tenants.
_SET_SEARCH_PATH_SQL = "SELECT set_config('search_path', :sp, true)"
_CURRENT_SEARCH_PATH_SQL = "SELECT current_setting('search_path')"

# Schémas système PostgreSQL : jamais un tenant (pg_* est réservé, `public` est
# le schéma partagé que l'isolation est censée masquer).
_RESERVED_TENANTS = frozenset({"public", "information_schema"})


def _validate_tenant(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or not _VALID_TENANT.fullmatch(tenant_id):
        raise ValueError(
            f"tenant_id invalide : {tenant_id!r} "
            "(caractères autorisés : a-z A-Z 0-9 _ -, 1 à 63 caractères)"
        )
    lowered = tenant_id.lower()
    if lowered in _RESERVED_TENANTS or lowered.startswith("pg_"):
        raise ValueError(
            f"tenant_id réservé : {tenant_id!r} "
            "(public, information_schema et pg_* sont des schémas système)"
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
        return _validate_tenant(
            self._static_tenant
            if self._static_tenant is not None
            else _current_tenant_id.get()
        )

    def _k(self, key: str) -> str:
        return f"{self._tenant}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
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

    async def get_or_set(self, key: str, factory: Any, ttl: int | None = None) -> Any:
        value = await self.get(key)
        if value is None:
            value = await factory() if callable(factory) else factory
            await self.set(key, value, ttl=ttl)
        return value

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        prefixed = [self._k(k) for k in keys]
        raw = await self._cache.mget(prefixed) if hasattr(self._cache, "mget") else {}
        prefix = f"{self._tenant}:"
        return {k[len(prefix) :]: v for k, v in raw.items()}

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> None:
        if hasattr(self._cache, "mset"):
            prefixed = {self._k(k): v for k, v in mapping.items()}
            await self._cache.mset(prefixed, ttl=ttl)
        else:
            for k, v in mapping.items():
                await self.set(k, v, ttl=ttl)

    async def disconnect(self) -> None:
        if hasattr(self._cache, "disconnect"):
            await self._cache.disconnect()

    async def ping(self) -> bool:
        if hasattr(self._cache, "ping"):
            return await self._cache.ping()
        return True

    def stats(self) -> dict:
        if hasattr(self._cache, "stats"):
            return self._cache.stats()
        return {"backend": "tenant_aware_cache", "tenant": self._tenant}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cache, name)


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _as_statement(query: Any) -> Any:
    """SQLAlchemy 2.x refuse le SQL brut : une chaîne devient `text()`."""
    if isinstance(query, str):
        from sqlalchemy import text

        return text(query)
    return query


class TenantAwareDB:
    """
    Wrapper sur la DB qui isole par tenant via search_path PostgreSQL.

    tenant_id optionnel :
      - fourni → tenant statique
      - absent  → tenant lu depuis _current_tenant_id (ContextVar)
    Le search_path est posé par transaction avec un identifiant validé et cité
    (voir `_set_tenant_schema`). Pour MySQL, SQLite ou MongoDB il est ignoré.
    Le schéma du tenant doit déjà exister ; sinon PostgreSQL retombe sur `public`.
    Attention : `.engine` et `__getattr__` exposent la DB brute, non isolée.
    """

    def __init__(self, db: Any, tenant_id: str | None = None) -> None:
        self._db = db
        self._static_tenant = tenant_id

    @property
    def _tenant(self) -> str:
        return _validate_tenant(
            self._static_tenant
            if self._static_tenant is not None
            else _current_tenant_id.get()
        )

    async def _set_tenant_schema(self, sess: Any) -> None:
        """
        Positionne le search_path du tenant, limité à la transaction courante.

        - Identifiant validé (regex stricte) puis cité ; la valeur est passée en
          paramètre lié à `set_config(..., true)` : aucune interpolation SQL.
        - Portée transaction (équivalent `SET LOCAL`) : rien ne fuit vers la
          requête suivante du pool, même si le reset du pool est désactivé.
          Un listener `after_begin` le pose au début de CHAQUE transaction
          de la session (autobegin, `begin()` du plugin, après `commit()`), sans
          exécuter de SQL à l'entrée (sinon `session.begin()` échouerait).
        - PostgreSQL uniquement. Les autres dialectes (SQLite, MySQL) et les
          adapters non SQL (MongoDB) sont ignorés. Une erreur sur PostgreSQL
          est propagée : une isolation qui échoue ne doit jamais être silencieuse.
        """
        tenant = _validate_tenant(self._tenant)
        get_bind = getattr(sess, "get_bind", None)
        if get_bind is None or get_bind().dialect.name != "postgresql":
            logger.debug("tenant search_path skipped, not postgresql", tenant=tenant)
            return

        from sqlalchemy import event, text

        params = {"sp": f'"{tenant}", public'}

        # Aucune requête ici : exécuter du SQL à l'entrée déclencherait
        # l'autobegin et casserait `async with session.begin():` côté plugin
        # ("A transaction is already begun"). Le search_path est posé par un
        # listener `after_begin`, au tout début de CHAQUE transaction de la
        # session (autobegin, `begin()`, après commit/rollback), donc dans la
        # même transaction que les requêtes du plugin.
        def _apply_conn(connection: Any) -> None:
            connection.execute(text(_SET_SEARCH_PATH_SQL), params)
            # Preuve que la valeur tient : en AUTOCOMMIT (ou derrière un pooler
            # transactionnel) chaque instruction est sa propre transaction et le
            # set_config local est perdu sans erreur. On refuse plutôt que de
            # lire silencieusement le schéma public.
            current = connection.execute(text(_CURRENT_SEARCH_PATH_SQL)).scalar()
            if current != params["sp"]:
                raise RuntimeError(
                    "isolation tenant impossible : le search_path n'a pas "
                    "persisté dans la transaction (isolation_level AUTOCOMMIT "
                    "ou pooler en mode statement ?). Désactivez AUTOCOMMIT pour "
                    "les bases utilisées avec tenancy.isolate_db, ou isolate_db."
                )

        def _on_begin(_session: Any, _transaction: Any, connection: Any) -> None:
            _apply_conn(connection)

        sync_sess = getattr(sess, "sync_session", sess)
        event.listen(sync_sess, "after_begin", _on_begin)
        # Transaction déjà ouverte par l'adapter (ex. `execution_options`
        # appliquées via `sess.connection()`) : `after_begin` est passé, on pose
        # le search_path tout de suite (le plugin ne pourrait de toute façon
        # plus appeler `begin()` sur cette session).
        if sync_sess.in_transaction():
            conn = await _maybe_await(sess.connection())
            await _maybe_await(conn.run_sync(_apply_conn))

    @contextlib.asynccontextmanager
    async def session(self):
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            yield sess

    async def execute(self, query: Any, *args, **kwargs) -> Any:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            return await sess.execute(_as_statement(query), *args, **kwargs)

    async def fetch_one(self, query: Any, *args, **kwargs) -> Any:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            if hasattr(sess, "fetch_one"):
                return await sess.fetch_one(query, *args, **kwargs)
            res = await sess.execute(_as_statement(query), *args, **kwargs)
            return res.mappings().first()

    async def fetch_all(self, query: Any, *args, **kwargs) -> list:
        async with self._db.session() as sess:
            await self._set_tenant_schema(sess)
            if hasattr(sess, "fetch_all"):
                return await sess.fetch_all(query, *args, **kwargs)
            res = await sess.execute(_as_statement(query), *args, **kwargs)
            return list(res.mappings().all())

    async def connect(self) -> None:
        if hasattr(self._db, "connect"):
            await self._db.connect()

    async def disconnect(self) -> None:
        if hasattr(self._db, "disconnect"):
            await self._db.disconnect()

    async def ping(self) -> tuple[bool, str]:
        if hasattr(self._db, "ping"):
            return await self._db.ping()
        return True, "ok"

    def status(self) -> dict:
        if hasattr(self._db, "status"):
            return self._db.status()
        return {"backend": "tenant_aware_db", "tenant": self._tenant}

    @property
    def engine(self) -> Any:
        return getattr(self._db, "engine", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._db, name)


def _bind_tenant(func: Any, tenant: str) -> Any:
    """Enveloppe `func` pour poser le ContextVar tenant pendant son exécution."""
    # Un objet dont `__call__` est async n'est pas une coroutine function : sans
    # cette détection le ContextVar serait remis à zéro avant l'await.
    if inspect.iscoroutinefunction(func) or inspect.iscoroutinefunction(
        getattr(func, "__call__", None)
    ):

        @functools.wraps(func)
        async def _async_wrapper(*a: Any, **k: Any) -> Any:
            token = _current_tenant_id.set(tenant)
            try:
                return await func(*a, **k)
            finally:
                _current_tenant_id.reset(token)

        return _async_wrapper

    @functools.wraps(func)
    def _wrapper(*a: Any, **k: Any) -> Any:
        token = _current_tenant_id.set(tenant)
        try:
            return func(*a, **k)
        finally:
            _current_tenant_id.reset(token)

    return _wrapper


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
        return _validate_tenant(
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
        # Sans identifiant explicite, le scheduler retient le nom de la fonction :
        # on le préfixe aussi, sinon deux tenants se remplacent mutuellement
        # (replace_existing=True).
        raw_id = id or job_id or getattr(func, "__name__", None)
        if raw_id is not None:
            kwargs["job_id"] = self._jid(raw_id)
        # Le job s'exécute hors du contexte de la requête : on fige le tenant
        # d'enregistrement pour que DB/cache du job visent le bon tenant.
        return self._scheduler.add_job(
            _bind_tenant(func, self._tenant), *args, **kwargs
        )

    def cron(self, expression: str, job_id: str | None = None):
        """@scheduler.cron : même préfixage tenant que add_job (sinon le job
        n'est pas retrouvable par remove_job / le ramasse-miette du plugin)."""

        def decorator(fn: Any) -> Any:
            raw_id = job_id or getattr(fn, "__name__", None)
            self._scheduler.cron(expression, job_id=self._jid(raw_id))(
                _bind_tenant(fn, self._tenant)
            )
            return fn

        return decorator

    def interval(self, **kwargs) -> Any:
        def decorator(fn: Any) -> Any:
            self.add_job(fn, "interval", **kwargs)
            return fn

        return decorator

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

    async def start(self) -> None:
        if hasattr(self._scheduler, "start"):
            await self._scheduler.start()

    async def shutdown(self, wait: bool = True) -> None:
        if hasattr(self._scheduler, "shutdown"):
            self._scheduler.shutdown(wait=wait)

    async def health_check(self) -> tuple[bool, str]:
        if hasattr(self._scheduler, "health_check"):
            return await self._scheduler.health_check()
        return True, "ok"

    def status(self) -> dict:
        if hasattr(self._scheduler, "status"):
            return self._scheduler.status()
        return {"backend": "tenant_aware_scheduler", "tenant": self._tenant}

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
    try:
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        from xcore.services.database.adapters.base import DBAdapter
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        from xcore.services.database.adapters.sql import SQLAdapter

        return isinstance(svc, (SQLAdapter, AsyncSQLAdapter, MongoDBAdapter, DBAdapter))
    except ImportError:
        # Fallback: class name suffix detection si les adapters ne sont pas installés
        cls_name = type(svc).__name__
        return any(
            cls_name.endswith(suffix)
            for suffix in (
                "SQLAdapter",
                "AsyncSQLAdapter",
                "MongoDBAdapter",
                "DBAdapter",
            )
        )

"""
Isolation tenant réelle : vrai PostgreSQL (optionnel), vrais SQLAlchemy/cache.

Les tests PostgreSQL sont ignorés sauf si ``XCORE_TEST_PG_URL`` est défini
(ex. ``postgresql+asyncpg://postgres@127.0.0.1:54331/postgres``).
"""

from __future__ import annotations

import os

import pytest

from xcore.configurations.sections import DatabaseConfig
from xcore.kernel.tenancy.services import (
    TenantAwareCache,
    TenantAwareDB,
    TenantAwareScheduler,
    _current_tenant_id,
)
from xcore.services.cache.backends.memory import MemoryBackend
from xcore.services.database.adapters.async_sql import AsyncSQLAdapter

PG_URL = os.environ.get("XCORE_TEST_PG_URL")
needs_pg = pytest.mark.skipif(not PG_URL, reason="XCORE_TEST_PG_URL non défini")


@pytest.fixture
async def pg_adapter():
    """Schémas acme/beta/public, une table `invoices` chacun, un pool d'1 conn."""
    from sqlalchemy import text

    adapter = AsyncSQLAdapter("pg", DatabaseConfig(url=PG_URL))
    await adapter.connect()
    async with adapter.engine.begin() as conn:
        for schema in ("acme", "beta"):
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'CREATE TABLE "{schema}".invoices (owner text)'))
            await conn.execute(
                text(f"INSERT INTO \"{schema}\".invoices VALUES ('{schema}-row')")
            )
        await conn.execute(text("DROP TABLE IF EXISTS public.invoices"))
        await conn.execute(text("CREATE TABLE public.invoices (owner text)"))
        await conn.execute(text("INSERT INTO public.invoices VALUES ('public-row')"))
    yield adapter
    async with adapter.engine.begin() as conn:
        for schema in ("acme", "beta"):
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await conn.execute(text("DROP TABLE public.invoices"))
    await adapter.disconnect()


async def _owners(tdb: TenantAwareDB) -> list[str]:
    res = await tdb.execute("SELECT owner FROM invoices ORDER BY owner")
    return [r[0] for r in res.fetchall()]


@needs_pg
async def test_pg_deux_tenants_voient_uniquement_leurs_donnees(pg_adapter):
    assert await _owners(TenantAwareDB(pg_adapter, "acme")) == ["acme-row"]
    assert await _owners(TenantAwareDB(pg_adapter, "beta")) == ["beta-row"]


@needs_pg
async def test_pg_contextvar_pilote_le_schema(pg_adapter):
    tdb = TenantAwareDB(pg_adapter)  # tenant lu depuis le ContextVar
    token = _current_tenant_id.set("beta")
    try:
        assert await _owners(tdb) == ["beta-row"]
    finally:
        _current_tenant_id.reset(token)


@needs_pg
async def test_pg_pas_de_fuite_de_search_path_dans_le_pool(pg_adapter):
    await _owners(TenantAwareDB(pg_adapter, "acme"))
    # La connexion revient au pool : une session brute ne doit pas voir acme.
    async with pg_adapter.session() as sess:
        from sqlalchemy import text

        rows = (await sess.execute(text("SELECT owner FROM invoices"))).fetchall()
        assert [r[0] for r in rows] == ["public-row"]


@needs_pg
async def test_pg_search_path_survit_a_un_commit_intermediaire(pg_adapter):
    from sqlalchemy import text

    tdb = TenantAwareDB(pg_adapter, "acme")
    async with tdb.session() as sess:
        await sess.commit()
        rows = (await sess.execute(text("SELECT owner FROM invoices"))).fetchall()
        assert [r[0] for r in rows] == ["acme-row"]


@needs_pg
async def test_pg_echec_du_set_search_path_n_est_pas_avale(pg_adapter, monkeypatch):
    tdb = TenantAwareDB(pg_adapter, "acme")
    monkeypatch.setattr(
        "xcore.kernel.tenancy.services._SET_SEARCH_PATH_SQL",
        "SELECT * FROM table_inexistante_xcore",
        raising=False,
    )
    with pytest.raises(Exception):
        await tdb.execute("SELECT 1")


@pytest.mark.parametrize(
    "bad",
    ['a"; DROP SCHEMA public CASCADE; --', "acme\n", "a b", "", "x" * 64, "é", "a:b"],
)
async def test_tenant_invalide_refuse_par_db_cache_scheduler(bad):
    class Sess:
        async def execute(self, *a, **k):  # pragma: no cover - ne doit pas arriver
            raise AssertionError("aucune requête avant validation")

    tdb = TenantAwareDB(object(), bad)
    with pytest.raises(ValueError):
        await tdb._set_tenant_schema(Sess())
    with pytest.raises(ValueError):
        await TenantAwareCache(MemoryBackend(), bad).get("k")
    with pytest.raises(ValueError):
        TenantAwareScheduler(object(), bad).get_jobs()


async def test_sqlite_set_search_path_ignore_proprement(tmp_path):
    adapter = AsyncSQLAdapter(
        "lite", DatabaseConfig(url=f"sqlite+aiosqlite:///{tmp_path}/t.db")
    )
    await adapter.connect()
    try:
        res = await TenantAwareDB(adapter, "acme").execute("SELECT 1")
        assert res.scalar() == 1
    finally:
        await adapter.disconnect()


async def test_cache_deux_tenants_reels_et_pas_de_glob_cross_tenant():
    backend = MemoryBackend()
    a, b = TenantAwareCache(backend, "acme"), TenantAwareCache(backend, "beta")
    await a.set("k", 1)
    await b.set("k", 2)
    assert await a.get("k") == 1 and await b.get("k") == 2
    assert await a.keys() == ["k"]
    # Un tenant "*" (en-tête non authentifié) ne doit ni lire ni purger les autres.
    with pytest.raises(ValueError):
        await TenantAwareCache(backend, "*").clear()
    assert await a.get("k") == 1


async def test_scheduler_job_sans_id_est_prefixe_et_tenant_propage():
    seen: list[str] = []

    class Backend:
        def __init__(self):
            self.jobs = {}

        def add_job(self, func, trigger="cron", job_id=None, **kw):
            self.jobs[job_id] = func

    backend = Backend()

    async def cleanup():
        seen.append(_current_tenant_id.get())

    TenantAwareScheduler(backend, "acme").add_job(cleanup)
    TenantAwareScheduler(backend, "beta").add_job(cleanup)
    assert sorted(backend.jobs) == ["acme:cleanup", "beta:cleanup"]
    for jid in sorted(backend.jobs):
        await backend.jobs[jid]()  # exécution hors requête : ContextVar à "default"
    assert seen == ["acme", "beta"]

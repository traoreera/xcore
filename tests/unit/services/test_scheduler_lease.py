"""#317 — verrou du scheduler tenu par la base (`backend: database`).

Testé contre de vraies bases SQLite (fichier partagé entre plusieurs moteurs, donc
entre plusieurs « workers »), et contre PostgreSQL quand XCORE_TEST_PG_URL est défini.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import textwrap

import pytest

import xcore.services.scheduler.service as svc_mod
from xcore.configurations.sections import DatabaseConfig, SchedulerConfig
from xcore.services.base import ServiceStatus
from xcore.services.scheduler.lease import TABLE, DatabaseLease, LeaseUnavailable

pytest.importorskip("aiosqlite")

PG_URL = os.environ.get("XCORE_TEST_PG_URL")


async def _async_adapter(url: str, name: str = "db"):
    from xcore.services.database.adapters.async_sql import AsyncSQLAdapter

    adapter = AsyncSQLAdapter(name, DatabaseConfig(name=name, type="sqlasync", url=url))
    await adapter.connect()
    return adapter


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'leases.sqlite3'}"


@pytest.fixture
async def workers(db_url):
    """Deux adaptateurs = deux processus : moteurs et pools distincts, même base."""
    a, b = await _async_adapter(db_url), await _async_adapter(db_url)
    yield a, b
    await a.disconnect()
    await b.disconnect()


@pytest.fixture(autouse=True)
def _clean_module_state():
    yield
    svc_mod._DB_LEASE = None
    svc_mod._JOB_REGISTRY.pop("j", None)


async def _lease(adapter, **kwargs) -> DatabaseLease:
    lease = DatabaseLease(adapter, **{"ttl": 30, "min_hold": 0, **kwargs})
    await lease.setup()
    return lease


class TestLeaseProtocol:
    async def test_first_wins_the_other_skips(self, workers):
        a, b = await _lease(workers[0]), await _lease(workers[1])
        assert await a.acquire("payroll", "A") is True
        assert await b.acquire("payroll", "B") is False
        assert await b.holder("payroll") == "A"

    async def test_leases_are_per_job(self, workers):
        a, b = await _lease(workers[0]), await _lease(workers[1])
        assert await a.acquire("payroll", "A")
        assert await b.acquire("depreciation", "B")

    async def test_release_frees_the_lease(self, workers):
        a, b = await _lease(workers[0]), await _lease(workers[1])
        await a.acquire("j", "A")
        await a.release("j", "A")
        assert await a.holder("j") is None
        assert await b.acquire("j", "B") is True

    async def test_release_never_frees_someone_elses_lease(self, workers):
        a, b = await _lease(workers[0]), await _lease(workers[1])
        await a.acquire("j", "A")
        await b.release("j", "B")  # B n'a jamais tenu ce bail
        assert await b.holder("j") == "A"
        assert await b.acquire("j", "B") is False

    async def test_expired_lease_is_taken_over(self, workers):
        a = await _lease(workers[0], ttl=0.05)
        b = await _lease(workers[1])
        await a.acquire("j", "A")
        assert await b.acquire("j", "B") is False
        await asyncio.sleep(0.15)
        assert await b.acquire("j", "B") is True
        # L'ancien propriétaire revient : il ne peut ni prolonger ni libérer.
        assert await a.renew("j", "A") is False
        await a.release("j", "A")
        assert await a.holder("j") == "B"

    async def test_renew_keeps_a_long_job_from_being_robbed(self, workers):
        a = await _lease(workers[0], ttl=0.2)
        b = await _lease(workers[1])
        await a.acquire("j", "A")
        for _ in range(4):
            await asyncio.sleep(0.1)
            assert await a.renew("j", "A") is True
        assert await b.acquire("j", "B") is False

    async def test_min_hold_survives_a_fast_job(self, workers):
        """Un job de 10 ms ne doit pas être rejoué par le processus en retard de 50 ms."""
        a = await _lease(workers[0], min_hold=0.4)
        b = await _lease(workers[1], min_hold=0.4)
        await a.acquire("j", "A")
        await a.release("j", "A")  # job déjà fini
        assert await b.acquire("j", "B") is False  # le second processus arrive
        await asyncio.sleep(0.5)
        assert await b.acquire("j", "B") is True  # déclenchement suivant

    async def test_release_after_min_hold_deletes_the_row(self, workers):
        a = await _lease(workers[0], min_hold=0.05)
        await a.acquire("j", "A")
        await asyncio.sleep(0.1)
        await a.release("j", "A")
        assert await a.holder("j") is None

    async def test_concurrent_acquire_has_exactly_one_winner(self, db_url):
        adapters = [await _async_adapter(db_url) for _ in range(6)]
        try:
            leases = [await _lease(adapter) for adapter in adapters]
            results = await asyncio.gather(
                *[lease.acquire("j", f"w{i}") for i, lease in enumerate(leases)]
            )
            assert sum(results) == 1
        finally:
            for adapter in adapters:
                await adapter.disconnect()

    async def test_setup_is_idempotent(self, workers):
        lease = await _lease(workers[0])
        await lease.setup()
        await (await _lease(workers[1])).setup()

    async def test_sync_adapter_is_supported(self, tmp_path):
        from xcore.services.database.adapters.sql import SQLAdapter

        url = f"sqlite:///{tmp_path / 'sync.sqlite3'}"
        adapters = [
            SQLAdapter("db", DatabaseConfig(name="db", type="sqlite", url=url))
            for _ in range(2)
        ]
        for adapter in adapters:
            await adapter.connect()
        try:
            a, b = await _lease(adapters[0]), await _lease(adapters[1])
            assert await a.acquire("j", "A") is True
            assert await b.acquire("j", "B") is False
            await a.release("j", "A")
            assert await b.acquire("j", "B") is True
        finally:
            for adapter in adapters:
                await adapter.disconnect()


class TestLeaseRefusals:
    def test_not_a_sql_adapter(self):
        with pytest.raises(LeaseUnavailable, match="base SQL"):
            DatabaseLease(object())

    def test_unsupported_dialect(self):
        class Engine:
            class dialect:
                name = "oracle"

        class Adapter:
            _engine = Engine()

        with pytest.raises(LeaseUnavailable, match="oracle"):
            DatabaseLease(Adapter())

    async def test_table_name_is_validated(self, workers):
        with pytest.raises(LeaseUnavailable, match="table"):
            DatabaseLease(workers[0], table="x; DROP TABLE y")

    def test_mysql_statements_use_insert_ignore(self):
        class Engine:
            class dialect:
                name = "mysql"

        class Adapter:
            _engine = Engine()

        lease = DatabaseLease(Adapter())
        assert "acquire" not in lease._sql
        assert lease._sql["insert"].startswith("INSERT IGNORE")
        assert "UNIX_TIMESTAMP" in lease._sql["steal"]


class TestDispatchWithLease:
    async def test_only_one_of_two_workers_runs_the_job(self, workers):
        """Deux processus reçoivent le même déclenchement : un seul exécute."""
        runs: list[str] = []
        a, b = await _lease(workers[0], min_hold=5), await _lease(
            workers[1], min_hold=5
        )

        async def job():
            runs.append("ran")

        svc_mod._JOB_REGISTRY["j"] = job
        for lease in (a, b):  # chaque « processus » a son propre bail
            svc_mod._DB_LEASE = lease
            await svc_mod._dispatch_job("j")
        assert runs == ["ran"]

    async def test_lease_is_held_while_the_job_runs_then_released(self, workers):
        a, b = await _lease(workers[0]), await _lease(workers[1])
        seen = []

        async def job():
            seen.append(await b.acquire("j", "intrus"))

        svc_mod._JOB_REGISTRY["j"] = job
        svc_mod._DB_LEASE = a
        await svc_mod._dispatch_job("j")
        assert seen == [False]
        assert await a.holder("j") is None

    async def test_lease_is_released_when_the_job_raises(self, workers):
        a = await _lease(workers[0])

        async def job():
            raise RuntimeError("boom")

        svc_mod._JOB_REGISTRY["j"] = job
        svc_mod._DB_LEASE = a
        with pytest.raises(RuntimeError):
            await svc_mod._dispatch_job("j")
        assert await a.holder("j") is None

    async def test_long_job_renews_its_lease(self, workers, monkeypatch):
        a = await _lease(workers[0], ttl=0.15)
        b = await _lease(workers[1])
        stolen = []

        async def job():
            await asyncio.sleep(0.5)  # plus de trois TTL
            stolen.append(await b.acquire("j", "B"))

        svc_mod._JOB_REGISTRY["j"] = job
        svc_mod._DB_LEASE = a
        await svc_mod._dispatch_job("j")
        assert stolen == [False]

    async def test_unreachable_database_skips_the_run(self, workers):
        """Sans réponse de la base on ne sait pas qui tient le bail : on n'exécute pas."""
        a = await _lease(workers[0])
        await workers[0].disconnect()
        a._engine = None  # moteur disparu : toute requête échoue
        runs = []
        svc_mod._JOB_REGISTRY["j"] = lambda: runs.append(1)
        svc_mod._DB_LEASE = a
        await svc_mod._dispatch_job("j")
        assert runs == []


class TestServiceWiring:
    async def test_backend_database_installs_the_lease(self, workers):
        svc = svc_mod.SchedulerService(
            SchedulerConfig(backend="database"), databases={"db": workers[0]}
        )
        await svc.init()
        try:
            assert svc._status is ServiceStatus.READY
            assert svc.status()["distributed_lock"] is True
            assert isinstance(svc_mod._DB_LEASE, DatabaseLease)
            assert svc_mod._DB_LEASE.table == TABLE
        finally:
            await svc.shutdown()
        assert svc_mod._DB_LEASE is None

    async def test_named_database_is_used(self, workers):
        svc = svc_mod.SchedulerService(
            SchedulerConfig(backend="database", database="jobs"),
            databases={"db": object(), "jobs": workers[1]},
        )
        await svc.init()
        try:
            assert svc._status is ServiceStatus.READY
        finally:
            await svc.shutdown()

    async def test_no_database_is_an_error_not_a_silent_fallback(self, caplog):
        svc = svc_mod.SchedulerService(SchedulerConfig(backend="database"))
        with caplog.at_level("ERROR", logger="xcore.services.scheduler"):
            await svc.init()
        try:
            assert svc._status is ServiceStatus.DEGRADED
            assert svc.status()["distributed_lock"] is False
            assert any("verrou en base" in r.getMessage() for r in caplog.records)
        finally:
            await svc.shutdown()

    async def test_non_sql_connection_is_an_error(self):
        svc = svc_mod.SchedulerService(
            SchedulerConfig(backend="database"), databases={"db": object()}
        )
        await svc.init()
        try:
            assert svc._status is ServiceStatus.DEGRADED
        finally:
            await svc.shutdown()

    async def test_container_hands_the_databases_to_the_scheduler(self, db_url):
        from xcore.configurations.sections import ServicesConfig
        from xcore.services.container import ServiceContainer

        container = ServiceContainer(
            ServicesConfig(
                databases={
                    "db": DatabaseConfig(name="db", type="sqlasync", url=db_url)
                },
                scheduler=SchedulerConfig(backend="database"),
            )
        )
        container.load_default_providers()
        await container.init()
        try:
            assert container.get("scheduler").status()["distributed_lock"] is True
        finally:
            await container.shutdown()


# Un vrai processus par « worker uvicorn » : chacun tente de prendre le même bail.
_PROCESS = textwrap.dedent("""
    import asyncio, sys
    from xcore.configurations.sections import DatabaseConfig
    from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
    from xcore.services.scheduler.lease import DatabaseLease

    async def main():
        adapter = AsyncSQLAdapter("db", DatabaseConfig(name="db", type="sqlasync", url=sys.argv[1]))
        await adapter.connect()
        lease = DatabaseLease(adapter, ttl=30, min_hold=30)
        await lease.setup()
        won = await lease.acquire("payroll", sys.argv[2])
        if won:
            await lease.release("payroll", sys.argv[2])  # job « fini » aussitôt
        print("won" if won else "skipped")
        await adapter.disconnect()

    asyncio.run(main())
    """)


def test_real_processes_exactly_one_runs(db_url):
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _PROCESS, db_url, f"worker-{i}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(4)
    ]
    outputs = []
    for proc in procs:
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
        outputs.append(out.strip())
    assert sorted(outputs) == ["skipped", "skipped", "skipped", "won"]


@pytest.mark.skipif(not PG_URL, reason="XCORE_TEST_PG_URL non défini")
async def test_postgresql_lease_protocol():
    a, b = await _async_adapter(PG_URL), await _async_adapter(PG_URL)
    try:
        la, lb = await _lease(a, ttl=0.2), await _lease(b)
        await la.release("pg-job", "A")
        assert await la.acquire("pg-job", "A") is True
        assert await lb.acquire("pg-job", "B") is False
        await asyncio.sleep(0.4)
        assert await lb.acquire("pg-job", "B") is True
        await lb.release("pg-job", "B")
    finally:
        await a.disconnect()
        await b.disconnect()

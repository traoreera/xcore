"""#309 — outbox transactionnelle : un effet extérieur APRÈS le commit.

Vraie base (SQLite fichier), vraies transactions, et un vrai plugin pour le chemin
« le répartiteur appelle plugin.action par le superviseur ».
"""

from __future__ import annotations

import asyncio
import logging
import textwrap

import pytest

from xcore.configurations.sections import (
    DatabaseConfig,
    OutboxConfig,
    SchedulerConfig,
    ServicesConfig,
)
from xcore.kernel.tenancy.services import _current_tenant_id
from xcore.services.container import ServiceContainer
from xcore.services.outbox import DEAD, PENDING, SENT, OutboxError, OutboxService

pytest.importorskip("aiosqlite")


async def _adapter(tmp_path, name="outbox.sqlite3"):
    from xcore.services.database.adapters.async_sql import AsyncSQLAdapter

    url = f"sqlite+aiosqlite:///{tmp_path / name}"
    adapter = AsyncSQLAdapter("db", DatabaseConfig(name="db", type="sqlasync", url=url))
    await adapter.connect()
    return adapter


@pytest.fixture
async def db(tmp_path):
    adapter = await _adapter(tmp_path)
    await adapter.execute("SELECT 1")
    async with adapter.session() as session:
        from sqlalchemy import text

        await session.execute(text("CREATE TABLE invoices (id INTEGER PRIMARY KEY)"))
    yield adapter
    await adapter.disconnect()


def _config(**overrides) -> OutboxConfig:
    return OutboxConfig(
        **{"enabled": True, "backoff_seconds": 0.0, "poll_seconds": 0.05, **overrides}
    )


@pytest.fixture
async def outbox(db):
    service = OutboxService(_config(), db)
    await service.init()
    yield service
    await service.shutdown()


class Mailbox:
    """La tâche : un « serveur SMTP » qui note ce qu'il a reçu."""

    def __init__(self, fail: int = 0) -> None:
        self.sent: list[dict] = []
        self.fail = fail

    async def __call__(self, payload: dict) -> None:
        if self.fail > 0:
            self.fail -= 1
            raise RuntimeError("smtp indisponible")
        self.sent.append(payload)


async def _insert_invoice(session, invoice_id: int) -> None:
    from sqlalchemy import text

    await session.execute(
        text("INSERT INTO invoices (id) VALUES (:id)"), {"id": invoice_id}
    )


class TestTransactionalDeposit:
    async def test_commit_keeps_the_document_and_sends_once(self, db, outbox):
        mail = Mailbox()
        outbox.register("mail", "send", mail)
        async with db.session() as session:
            await _insert_invoice(session, 42)
            receipt = await outbox.defer(
                "mail", "send", {"invoice": 42}, session=session
            )
            assert receipt.deferred
            # Avant le commit : rien n'est visible du répartiteur, donc rien ne part.
            assert await outbox.dispatch_once() == 0
        assert await outbox.dispatch_once() == 1
        assert [m["invoice"] for m in mail.sent] == [42]
        assert await outbox.dispatch_once() == 0  # jamais deux fois

    async def test_rollback_sends_nothing(self, db, outbox):
        """Le cas du ticket : une écriture ultérieure échoue, le courriel ne part pas."""
        mail = Mailbox()
        outbox.register("mail", "send", mail)
        with pytest.raises(RuntimeError, match="écriture ultérieure"):
            async with db.session() as session:
                await _insert_invoice(session, 7)
                await outbox.defer("mail", "send", {"invoice": 7}, session=session)
                raise RuntimeError("écriture ultérieure en échec")
        assert await outbox.dispatch_once() == 0
        assert mail.sent == [] and await outbox.stats() == {}

    async def test_resubmit_with_the_same_key_sends_a_single_copy(self, db, outbox):
        mail = Mailbox()
        outbox.register("mail", "send", mail)
        for _ in range(2):  # la soumission, puis la re-soumission
            async with db.session() as session:
                receipt = await outbox.defer(
                    "mail",
                    "send",
                    {"invoice": 42},
                    key="invoice:42:submitted",
                    session=session,
                )
        assert receipt.deferred is False and receipt.id is None
        await outbox.dispatch_once()
        assert len(mail.sent) == 1

    async def test_duplicate_key_does_not_poison_the_callers_transaction(
        self, db, outbox
    ):
        await outbox.defer("mail", "send", {}, key="k")
        async with db.session() as session:
            await outbox.defer("mail", "send", {}, key="k", session=session)
            await _insert_invoice(session, 1)  # la transaction est toujours utilisable
        rows = (await db.execute("SELECT id FROM invoices")).fetchall()
        assert [r[0] for r in rows] == [1]

    async def test_sync_session_is_supported(self, tmp_path):
        from sqlalchemy import text

        from xcore.services.database.adapters.sql import SQLAdapter

        adapter = SQLAdapter(
            "db",
            DatabaseConfig(
                name="db", type="sqlite", url=f"sqlite:///{tmp_path / 's.db'}"
            ),
        )
        await adapter.connect()
        service = OutboxService(_config(), adapter)
        await service.init()
        try:
            mail = Mailbox()
            service.register("mail", "send", mail)
            with adapter.session() as session:
                session.execute(text("CREATE TABLE t (id INTEGER)"))
                await service.defer("mail", "send", {"n": 1}, session=session)
            assert await service.dispatch_once() == 1 and mail.sent[0]["n"] == 1
        finally:
            await service.shutdown()
            await adapter.disconnect()

    async def test_without_session_the_intent_is_committed_at_once(self, outbox):
        mail = Mailbox()
        outbox.register("mail", "send", mail)
        await outbox.defer("mail", "send", {"n": 1})
        assert await outbox.dispatch_once() == 1

    async def test_delay_postpones_the_first_attempt(self, outbox):
        mail = Mailbox()
        outbox.register("mail", "send", mail)
        await outbox.defer("mail", "send", {}, delay=0.3)
        assert await outbox.dispatch_once() == 0
        await asyncio.sleep(0.4)
        assert await outbox.dispatch_once() == 1

    @pytest.mark.parametrize(
        "args, kwargs",
        [
            (("", "send"), {}),
            (("mail", ""), {}),
            (("mail", "send", {"when": object()}), {}),
            (("mail", "send"), {"key": ""}),
            (("mail", "send"), {"key": "x" * 256}),
        ],
    )
    async def test_invalid_deposit_fails_inside_the_transaction(
        self, outbox, args, kwargs
    ):
        with pytest.raises(OutboxError):
            await outbox.defer(*args, **kwargs)


class TestDispatch:
    async def test_task_receives_the_envelope_and_the_tenant(self, outbox):
        seen = {}

        async def task(payload):
            seen["payload"] = payload
            seen["tenant"] = _current_tenant_id.get()

        outbox.register("mail", "send", task)
        token = _current_tenant_id.set("acme")
        try:
            receipt = await outbox.defer("mail", "send", {"to": "a@b.c"}, key="k1")
        finally:
            _current_tenant_id.reset(token)
        await outbox.dispatch_once()
        assert seen["tenant"] == "acme"
        assert seen["payload"]["to"] == "a@b.c"
        assert seen["payload"]["_outbox"] == {
            "id": receipt.id,
            "key": "k1",
            "attempt": 1,
        }

    async def test_failure_is_retried_then_sent(self, outbox, caplog):
        mail = Mailbox(fail=2)
        outbox.register("mail", "send", mail)
        await outbox.defer("mail", "send", {"n": 1})
        with caplog.at_level(logging.WARNING, logger="xcore.services.outbox"):
            for _ in range(3):
                await outbox.dispatch_once()
        assert len(mail.sent) == 1 and mail.sent[0]["_outbox"]["attempt"] == 3
        assert await outbox.stats() == {SENT: 1}
        retries = [r for r in caplog.records if "will retry" in r.getMessage()]
        assert [r.xcore_ctx["attempt"] for r in retries] == [1, 2]

    async def test_backoff_delays_the_next_attempt(self, db):
        service = OutboxService(_config(backoff_seconds=0.3), db)
        await service.init()
        try:
            mail = Mailbox(fail=1)
            service.register("mail", "send", mail)
            await service.defer("mail", "send", {})
            assert await service.dispatch_once() == 1  # échec
            assert await service.dispatch_once() == 0  # pas encore prête
            await asyncio.sleep(0.4)
            assert await service.dispatch_once() == 1 and len(mail.sent) == 1
        finally:
            await service.shutdown()

    def test_backoff_is_exponential_and_capped(self, db):
        service = OutboxService(_config(backoff_seconds=5, max_backoff_seconds=60), db)
        assert [service.backoff(n) for n in range(1, 7)] == [5, 10, 20, 40, 60, 60]

    async def test_dead_letter_after_max_attempts_and_requeue(self, db, caplog):
        service = OutboxService(_config(max_attempts=2), db)
        await service.init()
        try:
            mail = Mailbox(fail=2)
            service.register("mail", "send", mail)
            receipt = await service.defer("mail", "send", {"n": 1}, key="k")
            with caplog.at_level(logging.ERROR, logger="xcore.services.outbox"):
                await service.dispatch_once()
                await service.dispatch_once()
            assert await service.stats() == {DEAD: 1}
            assert await service.dispatch_once() == 0  # la file morte ne tourne plus
            dead = await service.list()
            assert dead[0]["id"] == receipt.id and dead[0]["attempts"] == 2
            assert dead[0]["last_error"] == "smtp indisponible"
            assert any("giving up" in r.getMessage() for r in caplog.records)

            assert await service.retry(receipt.id) is True
            assert await service.retry("inconnue") is False
            assert await service.dispatch_once() == 1 and len(mail.sent) == 1
        finally:
            await service.shutdown()

    async def test_error_response_from_a_plugin_is_a_failure(self, outbox):
        calls = []

        async def caller(plugin, action, payload, tenant_id):
            calls.append((plugin, action, tenant_id))
            return {"status": "error", "msg": "boîte pleine"}

        outbox.bind(caller)
        await outbox.defer("mail", "send", {})
        await outbox.dispatch_once()
        assert calls == [("mail", "send", "default")]
        pending = await outbox.list(PENDING)
        assert (
            pending[0]["attempts"] == 1 and pending[0]["last_error"] == "boîte pleine"
        )

    async def test_no_handler_and_no_caller_is_a_failure_not_a_loss(self, outbox):
        await outbox.defer("mail", "send", {})
        await outbox.dispatch_once()
        assert (await outbox.list(PENDING))[0]["attempts"] == 1

    async def test_two_dispatchers_send_each_intent_once(self, db):
        a, b = OutboxService(_config(), db), OutboxService(_config(), db)
        await a.init()
        await b.init()
        try:
            sent: list[int] = []

            async def task(payload):
                await asyncio.sleep(0.01)
                sent.append(payload["n"])

            for service in (a, b):
                service.register("mail", "send", task)
            for n in range(12):
                await a.defer("mail", "send", {"n": n})
            await asyncio.gather(a.dispatch_once(), b.dispatch_once())
            assert sorted(sent) == list(range(12))
        finally:
            await a.shutdown()
            await b.shutdown()

    async def test_crashed_dispatcher_lease_expires_and_another_takes_over(self, db):
        """Mort après l'envoi mais avant d'écrire `sent` : l'intention est renvoyée."""
        crashed = OutboxService(_config(lease_seconds=0.2), db)
        survivor = OutboxService(_config(), db)
        await crashed.init()
        await survivor.init()
        try:
            mail = Mailbox()
            survivor.register("mail", "send", mail)
            receipt = await crashed.defer("mail", "send", {})
            assert await crashed._claim(receipt.id) is not None  # puis le process meurt
            assert await survivor.dispatch_once() == 0  # bail encore tenu
            await asyncio.sleep(0.3)
            assert await survivor.dispatch_once() == 1 and len(mail.sent) == 1
        finally:
            await crashed.shutdown()
            await survivor.shutdown()

    async def test_stop_during_a_send_releases_the_intent_without_an_attempt(self, db):
        service = OutboxService(_config(), db)
        await service.init()
        started = asyncio.Event()

        async def slow(payload):
            started.set()
            await asyncio.sleep(30)

        service.register("mail", "send", slow)
        await service.defer("mail", "send", {})
        service.start()
        await asyncio.wait_for(started.wait(), timeout=5)
        await service.stop()
        pending = await service.list(PENDING)
        assert pending[0]["attempts"] == 0
        mail = Mailbox()
        service.register("mail", "send", mail)
        assert await service.dispatch_once() == 1  # reprise immédiate, bail rendu
        await service.shutdown()

    async def test_background_loop_delivers_and_notify_wakes_it(self, db):
        service = OutboxService(_config(poll_seconds=30), db)
        await service.init()
        try:
            delivered = asyncio.Event()
            service.register("mail", "send", lambda payload: delivered.set())
            service.start()
            service.start()  # idempotent
            await asyncio.sleep(0.05)  # la boucle dort pour 30 s
            async with db.session() as session:
                await service.defer("mail", "send", {}, session=session)
            service.notify()  # après le commit : pas d'attente du prochain tour
            await asyncio.wait_for(delivered.wait(), timeout=5)
        finally:
            await service.shutdown()

    async def test_sent_intents_are_purged_after_retention(self, db):
        service = OutboxService(_config(retention_seconds=0.1), db)
        await service.init()
        try:
            service.register("mail", "send", Mailbox())
            await service.defer("mail", "send", {}, key="k")
            await service.dispatch_once()
            await asyncio.sleep(0.2)
            await service._purge_if_due()
            assert await service.stats() == {}
            assert (
                await service.defer("mail", "send", {}, key="k")
            ).deferred  # clé libre
        finally:
            await service.shutdown()

    async def test_health_and_status(self, outbox):
        await outbox.defer("mail", "send", {})
        ok, message = await outbox.health_check()
        assert ok and "1 pending" in message
        assert outbox.status()["counts"] == {PENDING: 1}


class TestWiring:
    def _services(self, tmp_path, **outbox) -> ServicesConfig:
        return ServicesConfig(
            databases={
                "db": DatabaseConfig(
                    name="db",
                    type="sqlasync",
                    url=f"sqlite+aiosqlite:///{tmp_path / 'c.db'}",
                )
            },
            scheduler=SchedulerConfig(enabled=False),
            outbox=_config(**outbox),
        )

    async def test_disabled_by_default(self):
        container = ServiceContainer(
            ServicesConfig(scheduler=SchedulerConfig(enabled=False))
        )
        container.load_default_providers()
        await container.init()
        assert not container.has("outbox")
        await container.shutdown()

    async def test_enabled_registers_the_service(self, tmp_path):
        container = ServiceContainer(self._services(tmp_path))
        container.load_default_providers()
        await container.init()
        try:
            assert isinstance(container.get("outbox"), OutboxService)
        finally:
            await container.shutdown()

    async def test_no_database_stops_the_boot(self):
        container = ServiceContainer(
            ServicesConfig(scheduler=SchedulerConfig(enabled=False), outbox=_config())
        )
        container.load_default_providers()
        with pytest.raises(OutboxError, match="services.databases"):
            await container.init()

    def test_refusals(self):
        with pytest.raises(OutboxError, match="base SQL"):
            OutboxService(_config(), object())

    async def test_invalid_table_name(self, db):
        with pytest.raises(OutboxError, match="table"):
            OutboxService(_config(table="x; DROP"), db)

    def test_loader_reads_the_section(self, tmp_path):
        from xcore.configurations.loader import ConfigLoader

        cfg = tmp_path / "integration.yaml"
        cfg.write_text("services:\n  outbox:\n    enabled: true\n    max_attempts: 3\n")
        outbox = ConfigLoader.load(str(cfg)).services.outbox
        assert outbox.enabled and outbox.max_attempts == 3 and outbox.dispatch is True

    async def test_xcore_dispatches_to_a_plugin_action(self, tmp_path):
        """Bout en bout : dépôt, commit, le répartiteur appelle mail.send par le superviseur."""
        from xcore import Xcore

        plugin = tmp_path / "plugins" / "mail" / "src"
        plugin.mkdir(parents=True)
        (plugin.parent / "plugin.yaml").write_text(textwrap.dedent("""
            name: mail
            version: 1.0.0
            execution_mode: trusted
            permissions:
              - {resource: "*", actions: ["*"], effect: allow}
            """))
        (plugin / "main.py").write_text(textwrap.dedent("""
            from xcore import TrustedBase, ok

            SENT = []

            class Plugin(TrustedBase):
                async def handle(self, action, payload):
                    if action == "send":
                        SENT.append(payload)
                        return ok()
                    if action == "sent":
                        return ok(sent=list(SENT))
                    return ok()
            """))
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent(f"""
            app:
              secret_key: test-secret-key-for-testing-min32chars
            plugins:
              directory: {tmp_path / "plugins"}
              strict_trusted: false
              interval: 0
            services:
              databases:
                db:
                  type: sqlasync
                  url: sqlite+aiosqlite:///{tmp_path / "app.db"}
              scheduler:
                enabled: false
              outbox:
                enabled: true
                poll_seconds: 0.05
            """))
        app = Xcore(config_path=str(cfg))
        await app.boot()
        try:
            outbox, db = app.services.get("outbox"), app.services.get("db")
            assert outbox.status()["dispatching"] is True
            async with db.session() as session:
                await outbox.defer(
                    "mail", "send", {"to": "a@b.c"}, key="welcome:1", session=session
                )
            for _ in range(100):
                if (await outbox.stats()).get(SENT):
                    break
                await asyncio.sleep(0.05)
            result = await app.plugins.call("mail", "sent", {})
            assert [m["to"] for m in result["sent"]] == ["a@b.c"]
            assert result["sent"][0]["_outbox"]["key"] == "welcome:1"
        finally:
            await app.shutdown()
        assert outbox.status()["dispatching"] is False

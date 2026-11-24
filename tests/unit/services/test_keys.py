"""#312 — service `keys` : une clé par organisation, des versions, une rotation."""

from __future__ import annotations

import gc
import logging
import textwrap

import pytest

from xcore.configurations.loader import ConfigLoader
from xcore.configurations.sections import DatabaseConfig, KeysConfig, ServicesConfig
from xcore.kernel.tenancy.services import _current_tenant_id
from xcore.services.container import ServiceContainer
from xcore.services.keys import (
    DatabaseVersionStore,
    FileVersionStore,
    HKDFKeyProvider,
    KeyService,
    KeyServiceError,
    KeyVersion,
    MemoryVersionStore,
    UnknownKeyVersion,
    VersionConflict,
    hkdf_sha256,
)

MASTER = "m" * 48
MASTER_2 = "n" * 48


async def make(store=None, **cfg) -> KeyService:
    config = KeysConfig(
        **{"enabled": True, "master_key": MASTER, "refresh_seconds": 0, **cfg}
    )
    service = KeyService(config, store=store or MemoryVersionStore())
    await service.init()
    return service


class TestHKDF:
    def test_rfc5869_test_case_1(self):
        okm = hkdf_sha256(
            bytes.fromhex("0b" * 22),
            bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
            42,
            bytes.fromhex("000102030405060708090a0b0c"),
        )
        assert okm.hex() == (
            "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865"
        )

    def test_rfc5869_test_case_3_empty_salt_and_info(self):
        okm = hkdf_sha256(bytes.fromhex("0b" * 22), b"", 42)
        assert okm.hex() == (
            "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d"
            "9d201395faa4b61a96c8"
        )


class TestDerivation:
    async def test_key_is_32_bytes_and_stable(self):
        keys = await make()
        first = keys.data_key("acme", "doctype.password")
        again = (await make()).data_key("acme", "doctype.password")
        assert len(first.key) == 32 and first.key == again.key
        assert first.version == 1 and first.tenant_id == "acme"

    async def test_every_organisation_has_its_own_key(self):
        keys = await make()
        assert keys.data_key("acme", "p").key != keys.data_key("globex", "p").key

    async def test_every_purpose_has_its_own_key(self):
        keys = await make()
        assert keys.data_key("acme", "smtp").key != keys.data_key("acme", "imap").key

    async def test_field_boundaries_are_not_ambiguous(self):
        keys = await make()
        assert keys.data_key("ab", "c").key != keys.data_key("a", "bc").key

    async def test_a_different_master_key_gives_different_keys(self):
        a, b = await make(), await make(master_key=MASTER_2)
        assert a.data_key("acme", "p").key != b.data_key("acme", "p").key

    async def test_default_tenant_is_the_current_request_tenant(self):
        keys = await make()
        token = _current_tenant_id.set("acme")
        try:
            assert keys.data_key(purpose="p").key == keys.data_key("acme", "p").key
            assert keys.data_key(purpose="p").tenant_id == "acme"
        finally:
            _current_tenant_id.reset(token)

    async def test_key_never_appears_in_repr(self):
        key = (await make()).data_key("acme", "p")
        assert key.key.hex() not in repr(key) and "key=" not in repr(key)

    async def test_urlsafe_is_a_fernet_shaped_key(self):
        import base64

        key = (await make()).data_key("acme", "p")
        assert len(key.urlsafe()) == 44
        assert base64.urlsafe_b64decode(key.urlsafe()) == key.key

    async def test_empty_arguments_are_refused(self):
        keys = await make()
        with pytest.raises(KeyServiceError):
            keys.data_key("", "p")
        with pytest.raises(KeyServiceError):
            keys.data_key("acme", "")


class TestTagging:
    def test_tag_and_split_roundtrip(self):
        assert KeyService.tag(3, "gAAAA:x") == "v3:gAAAA:x"
        assert KeyService.split("v3:gAAAA:x") == (3, "gAAAA:x")

    def test_untagged_value_is_a_legacy_secret(self):
        assert KeyService.split("gAAAAlegacy") == (None, "gAAAAlegacy")

    async def test_is_current(self):
        keys = await make()
        assert keys.is_current("v1:abc", "acme")
        await keys.rotate("acme")
        assert not keys.is_current("v1:abc", "acme")
        assert keys.is_current("v2:abc", "acme")
        assert not keys.is_current("legacy", "acme")


class TestRotation:
    async def test_rotation_opens_a_new_version_and_keeps_the_old_readable(self):
        keys = await make()
        before = keys.data_key("acme", "p")
        result = await keys.rotate("acme")
        assert (result.old_version, result.new_version) == (1, 2)
        after = keys.data_key("acme", "p")
        assert after.version == 2 and after.key != before.key
        assert keys.data_key("acme", "p", version=1).key == before.key
        assert keys.versions("acme") == [1, 2]

    async def test_rotation_is_per_organisation(self):
        keys = await make()
        globex = keys.data_key("globex", "p")
        await keys.rotate("acme")
        assert keys.current_version("globex") == 1
        assert keys.data_key("globex", "p").key == globex.key

    async def test_unknown_version_is_an_error(self):
        keys = await make()
        with pytest.raises(UnknownKeyVersion, match="version 7"):
            keys.data_key("acme", "p", version=7)

    async def test_handlers_reseal_the_secrets(self):
        """Le scénario complet : sceller, tourner, tout est relisible sous la v2."""
        keys = await make()
        vault = {"smtp": keys.tag(1, "x" + keys.data_key("acme", "mail").key.hex())}

        async def reseal(tenant, old, new):
            for name, stored in vault.items():
                version, body = keys.split(stored)
                assert (
                    body
                    == "x" + keys.data_key(tenant, "mail", version=version).key.hex()
                )
                vault[name] = keys.tag(
                    new, "x" + keys.data_key(tenant, "mail").key.hex()
                )

        keys.on_rotate("mail", reseal)
        result = await keys.rotate("acme")
        assert result.ok and result.handlers == {"mail": "ok"}
        assert keys.is_current(vault["smtp"], "acme")

    async def test_sync_handler_is_supported(self):
        keys = await make()
        calls = []
        keys.on_rotate(
            "sync", lambda tenant, old, new: calls.append((tenant, old, new))
        )
        await keys.rotate("acme")
        assert calls == [("acme", 1, 2)]

    async def test_a_failing_handler_does_not_block_the_others(self, caplog):
        keys = await make()
        done = []

        def broken(tenant, old, new):
            raise RuntimeError("table verrouillée")

        keys.on_rotate("a_broken", broken)
        keys.on_rotate("b_fine", lambda *a: done.append(a))
        with caplog.at_level(logging.ERROR, logger="xcore.services.keys"):
            result = await keys.rotate("acme")
        assert not result.ok
        assert result.handlers == {"a_broken": "table verrouillée", "b_fine": "ok"}
        assert done and keys.current_version("acme") == 2  # la version reste ouverte

    async def test_reseal_retries_without_opening_a_version(self):
        keys = await make()
        calls = []
        await keys.rotate("acme")
        keys.on_rotate("mail", lambda *a: calls.append(a))
        result = await keys.reseal("acme")
        assert calls == [("acme", 1, 2)] and result.new_version == 2
        assert keys.versions("acme") == [1, 2]

    async def test_plugin_method_is_held_weakly(self):
        """Un plugin déchargé n'est pas épinglé par sa réécriture, qui disparaît avec lui."""
        keys = await make()

        class Plugin:
            def reseal(self, tenant, old, new):
                raise AssertionError("plugin déchargé : ne doit plus être appelé")

        plugin = Plugin()
        keys.on_rotate("plugin", plugin.reseal)
        del plugin
        gc.collect()
        result = await keys.rotate("acme")
        assert result.handlers == {}
        assert keys.status()["rotation_handlers"] == []

    async def test_off_rotate(self):
        keys = await make()
        keys.on_rotate("x", lambda *a: None)
        keys.off_rotate("x")
        assert (await keys.rotate("acme")).handlers == {}


class TestMasterKeyRotation:
    async def test_adding_a_master_key_does_not_change_keys_in_service(self):
        store = MemoryVersionStore()
        before = (await make(store)).data_key("acme", "p")
        keys = await make(store, master_keys={2: MASTER_2})
        assert keys.data_key("acme", "p").key == before.key  # v1 reste sous la clé n°1

    async def test_new_versions_use_the_newest_master_key(self):
        store = MemoryVersionStore()
        old_service = await make(store)
        v1 = old_service.data_key("acme", "p")
        keys = await make(store, master_keys={2: MASTER_2})
        await keys.rotate("acme")
        records = (await store.load())["acme"]
        assert [(r.version, r.master_id) for r in records] == [(1, 1), (2, 2)]
        assert keys.data_key("acme", "p", version=1).key == v1.key

    async def test_rotate_stale_only_touches_tenants_on_an_old_master_key(self):
        store = MemoryVersionStore()
        first = await make(store)
        await first.rotate("acme")  # acme connue du store, sous la clé n°1
        keys = await make(store, master_keys={2: MASTER_2})
        results = await keys.rotate_stale(tenants=["globex"])
        assert sorted(r.tenant_id for r in results) == ["acme", "globex"]
        assert await keys.rotate_stale(tenants=["globex"]) == []

    async def test_removed_master_key_is_a_clear_error(self):
        store = MemoryVersionStore()
        await (await make(store)).rotate("acme")
        keys = KeyService(
            KeysConfig(enabled=True, master_keys={2: MASTER_2}), store=store
        )
        await keys.init()
        with pytest.raises(KeyServiceError, match="clé maîtresse 1"):
            keys.data_key("acme", "p", version=1)


class TestConfiguration:
    async def test_short_master_key_refuses_to_start(self):
        with pytest.raises(KeyServiceError, match="trop courte"):
            await make(master_key="short")

    async def test_no_master_key_refuses_to_start(self):
        with pytest.raises(KeyServiceError, match="aucune clé"):
            await make(master_key=None)

    async def test_master_key_cannot_be_declared_twice(self):
        with pytest.raises(KeyServiceError, match="n°1"):
            await make(master_keys={1: MASTER_2})

    def test_loader_reads_the_section(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XCORE_TEST_MASTER_KEY", MASTER)
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent("""
            services:
              keys:
                enabled: true
                master_key: ${XCORE_TEST_MASTER_KEY}
                store: memory
                refresh_seconds: 5
            """))
        keys = ConfigLoader.load(str(cfg)).services.keys
        assert keys.enabled and keys.master_key == MASTER
        assert keys.store == "memory" and keys.refresh_seconds == 5

    def test_master_key_is_redacted_in_logs(self):
        from xcore.kernel.observability import get_logger

        fields = get_logger("xcore.test")._sanitize_fields({"master_key": MASTER})
        assert MASTER not in str(fields)

    async def test_health_and_status(self):
        keys = await make()
        assert await keys.health_check() == (True, "ok")
        status = keys.status()
        assert status["master_key_id"] == 1 and status["durable"] is False
        await keys.shutdown()

    async def test_memory_store_warns_that_it_is_not_durable(self, caplog):
        with caplog.at_level(logging.WARNING, logger="xcore.services.keys"):
            await make()
        assert any("mémoire" in r.getMessage() for r in caplog.records)


class TestStores:
    async def _sql_adapter(self, tmp_path):
        pytest.importorskip("aiosqlite")
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter

        url = f"sqlite+aiosqlite:///{tmp_path / 'keys.sqlite3'}"
        adapter = AsyncSQLAdapter(
            "db", DatabaseConfig(name="db", type="sqlasync", url=url)
        )
        await adapter.connect()
        return adapter

    @pytest.fixture(params=["memory", "file", "database"])
    async def store(self, request, tmp_path):
        if request.param == "memory":
            yield MemoryVersionStore()
        elif request.param == "file":
            yield FileVersionStore(tmp_path / "state" / "versions.json")
        else:
            adapter = await self._sql_adapter(tmp_path)
            yield DatabaseVersionStore(adapter)
            await adapter.disconnect()

    async def test_append_load_and_conflict(self, store):
        await store.setup()
        await store.setup()  # idempotent
        assert await store.load() == {}
        await store.append(KeyVersion("acme", 2, 1))
        await store.append(KeyVersion("acme", 1, 1))
        await store.append(KeyVersion("globex", 1, 2))
        loaded = await store.load()
        assert [v.version for v in loaded["acme"]] == [1, 2]
        assert loaded["globex"][0].master_id == 2
        with pytest.raises(VersionConflict):
            await store.append(KeyVersion("acme", 2, 1))

    async def test_rotation_survives_a_restart(self, tmp_path):
        path = tmp_path / "versions.json"
        first = await make(FileVersionStore(path))
        sealed_under = first.data_key("acme", "p")
        await first.rotate("acme")
        v2 = first.data_key("acme", "p")
        restarted = await make(FileVersionStore(path))
        assert restarted.current_version("acme") == 2
        assert restarted.data_key("acme", "p").key == v2.key
        assert restarted.data_key("acme", "p", version=1).key == sealed_under.key

    async def test_another_worker_sees_the_rotation_after_refresh(self, tmp_path):
        adapter = await self._sql_adapter(tmp_path)
        try:
            a = await make(DatabaseVersionStore(adapter))
            b = await make(DatabaseVersionStore(adapter))
            await a.rotate("acme")
            assert b.current_version("acme") == 1  # pas encore relu
            await b.refresh()
            assert b.current_version("acme") == 2
            assert b.data_key("acme", "p").key == a.data_key("acme", "p").key
        finally:
            await adapter.disconnect()

    async def test_concurrent_rotation_opens_a_single_version(self, tmp_path):
        """Deux workers tournent en même temps : une seule version 2, pas de version 3."""
        adapter = await self._sql_adapter(tmp_path)
        try:
            a = await make(DatabaseVersionStore(adapter))
            b = await make(DatabaseVersionStore(adapter))
            # b croit encore être en v1 quand a vient d'ouvrir la v2.
            original_refresh = b.refresh

            async def stale_refresh():
                b.refresh = original_refresh  # seulement la relecture d'entrée

            b.refresh = stale_refresh
            await a.rotate("acme")
            result = await b.rotate("acme")
            assert result.new_version == 2 and result.handlers == {}
            assert b.versions("acme") == [1, 2]
        finally:
            await adapter.disconnect()

    def test_database_store_refuses_a_non_sql_connection(self):
        with pytest.raises(ValueError, match="base SQL"):
            DatabaseVersionStore(object())


class TestContainer:
    def _config(self, **keys) -> ServicesConfig:
        from xcore.configurations.sections import SchedulerConfig

        return ServicesConfig(
            scheduler=SchedulerConfig(enabled=False),
            keys=KeysConfig(**{"enabled": True, "master_key": MASTER, **keys}),
        )

    async def test_disabled_by_default(self):
        container = ServiceContainer(ServicesConfig())
        container.load_default_providers()
        await container.init()
        try:
            assert not container.has("keys")
        finally:
            await container.shutdown()

    async def test_enabled_registers_the_service(self, tmp_path):
        container = ServiceContainer(
            self._config(store="file", path=str(tmp_path / "v.json"))
        )
        container.load_default_providers()
        await container.init()
        try:
            keys = container.get("keys")
            assert isinstance(keys, KeyService) and keys.status()["durable"] is True
        finally:
            await container.shutdown()

    async def test_database_store_uses_the_default_connection(self, tmp_path):
        pytest.importorskip("aiosqlite")
        config = self._config(store="database")
        config.databases = {
            "db": DatabaseConfig(
                name="db",
                type="sqlasync",
                url=f"sqlite+aiosqlite:///{tmp_path / 'k.db'}",
            )
        }
        container = ServiceContainer(config)
        container.load_default_providers()
        await container.init()
        try:
            await container.get("keys").rotate("acme")
            assert container.get("keys").current_version("acme") == 2
        finally:
            await container.shutdown()

    @pytest.mark.parametrize(
        "keys", [{"store": "database"}, {"store": "vault"}, {"master_key": "weak"}]
    )
    async def test_invalid_configuration_stops_the_boot(self, keys):
        container = ServiceContainer(self._config(**keys))
        container.load_default_providers()
        with pytest.raises(KeyServiceError):
            await container.init()
        await container.shutdown()

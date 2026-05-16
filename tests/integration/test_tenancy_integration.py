"""
tests/integration/test_tenancy_integration.py — Tests d'intégration multi-tenant.

Couvre :
  - Isolation cache : deux tenants ne partagent pas les mêmes clés
  - Isolation DB : search_path correctement appliqué par tenant
  - IPC : allowed_callers respecté dans le pipeline complet
  - Propagation tenant_id : HTTP → plugin context → IPC enfant
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def tenancy_config():
    from xcore.configurations.sections import TenancyConfig

    return TenancyConfig(
        enabled=True,
        header="X-Tenant-ID",
        subdomain=False,
        default_tenant="default",
        isolate_cache=True,
        isolate_db=True,
        isolate_scheduler=True,
        enforce_ipc=True,
    )


@pytest.fixture
def in_memory_cache():
    """Cache dict en mémoire simulant l'interface CacheService."""
    store = {}

    class FakeCache:
        async def get(self, key, default=None):
            return store.get(key, default)

        async def set(self, key, value, ttl=None):
            store[key] = value

        async def delete(self, key):
            store.pop(key, None)

        async def exists(self, key):
            return key in store

        async def incr(self, key, delta=1):
            store[key] = store.get(key, 0) + delta
            return store[key]

        async def keys(self, pattern="*"):
            import fnmatch

            return [k for k in store if fnmatch.fnmatch(k, pattern)]

        @property
        def _store(self):
            return store

    return FakeCache()


# ─────────────────────────────────────────────────────────────
# Isolation cache : deux tenants sont totalement séparés
# ─────────────────────────────────────────────────────────────


class TestCacheTenantIsolation:
    @pytest.mark.asyncio
    async def test_two_tenants_dont_share_keys(self, in_memory_cache):
        from xcore.kernel.tenancy.services import TenantAwareCache

        cache_acme = TenantAwareCache(in_memory_cache, "acme")
        cache_beta = TenantAwareCache(in_memory_cache, "beta")

        await cache_acme.set("balance", 100)
        await cache_beta.set("balance", 999)

        assert await cache_acme.get("balance") == 100
        assert await cache_beta.get("balance") == 999

    @pytest.mark.asyncio
    async def test_delete_affects_only_one_tenant(self, in_memory_cache):
        from xcore.kernel.tenancy.services import TenantAwareCache

        cache_acme = TenantAwareCache(in_memory_cache, "acme")
        cache_beta = TenantAwareCache(in_memory_cache, "beta")

        await cache_acme.set("token", "abc")
        await cache_beta.set("token", "xyz")
        await cache_acme.delete("token")

        assert await cache_acme.get("token") is None
        assert await cache_beta.get("token") == "xyz"

    @pytest.mark.asyncio
    async def test_clear_scoped_to_tenant(self, in_memory_cache):
        from xcore.kernel.tenancy.services import TenantAwareCache

        cache_acme = TenantAwareCache(in_memory_cache, "acme")
        cache_beta = TenantAwareCache(in_memory_cache, "beta")

        await cache_acme.set("a", 1)
        await cache_acme.set("b", 2)
        await cache_beta.set("a", 3)

        await cache_acme.clear("*")

        assert await cache_acme.get("a") is None
        assert await cache_acme.get("b") is None
        assert await cache_beta.get("a") == 3  # beta intact

    @pytest.mark.asyncio
    async def test_incr_isolated_per_tenant(self, in_memory_cache):
        from xcore.kernel.tenancy.services import TenantAwareCache

        cache_acme = TenantAwareCache(in_memory_cache, "acme")
        cache_beta = TenantAwareCache(in_memory_cache, "beta")

        await cache_acme.incr("hits")
        await cache_acme.incr("hits")
        await cache_beta.incr("hits")

        assert await cache_acme.get("hits") == 2
        assert await cache_beta.get("hits") == 1


# ─────────────────────────────────────────────────────────────
# Isolation DB : search_path par tenant
# ─────────────────────────────────────────────────────────────


class TestDBTenantIsolation:
    @pytest.mark.asyncio
    async def test_each_session_sets_search_path(self):
        import contextlib

        from xcore.kernel.tenancy.services import TenantAwareDB

        executed = []

        class FakeSess:
            async def execute(self, query, *a, **kw):
                executed.append(query)
                return "ok"

            async def fetch_one(self, q, *a, **kw):
                executed.append(q)
                return {}

            async def fetch_all(self, q, *a, **kw):
                executed.append(q)
                return []

        @contextlib.asynccontextmanager
        async def fake_session():
            yield FakeSess()

        db = MagicMock()
        db.session = fake_session

        tdb = TenantAwareDB(db, "acme")
        await tdb.execute("SELECT 1")

        assert any("SET search_path TO acme" in q for q in executed)

    @pytest.mark.asyncio
    async def test_two_tenants_set_different_search_paths(self):
        import contextlib

        from xcore.kernel.tenancy.services import TenantAwareDB

        paths = []

        class FakeSess:
            async def execute(self, query, *a, **kw):
                paths.append(query)
                return "ok"

            async def fetch_all(self, q, *a, **kw):
                paths.append(q)
                return []

        @contextlib.asynccontextmanager
        async def fake_session():
            yield FakeSess()

        db = MagicMock()
        db.session = fake_session

        tdb_acme = TenantAwareDB(db, "acme")
        tdb_beta = TenantAwareDB(db, "beta")

        await tdb_acme.execute("SELECT 1")
        await tdb_beta.execute("SELECT 1")

        acme_paths = [p for p in paths if "acme" in p]
        beta_paths = [p for p in paths if "beta" in p]
        assert acme_paths
        assert beta_paths


# ─────────────────────────────────────────────────────────────
# IPC : pipeline complet avec allowed_callers
# ─────────────────────────────────────────────────────────────


class TestIPCPipelineIntegration:
    def _make_supervisor(self, enforce_ipc=True):
        from xcore.configurations.sections import TenancyConfig
        from xcore.kernel.context import KernelContext
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        config = MagicMock()
        config.tenancy = TenancyConfig(enforce_ipc=enforce_ipc)

        services = MagicMock()
        services.as_dict.return_value = {}

        ctx = KernelContext(
            config=config,
            services=services,
            events=MagicMock(),
            hooks=MagicMock(),
            registry=MagicMock(),
            metrics=MagicMock(),
            tracer=MagicMock(),
            health=MagicMock(),
        )
        return PluginSupervisor(ctx)

    def _make_handler(self, allowed_callers):
        manifest = MagicMock()
        manifest.allowed_callers = allowed_callers
        handler = MagicMock()
        handler.manifest = manifest
        handler.call = AsyncMock(return_value={"status": "ok"})
        return handler

    @pytest.mark.asyncio
    async def test_ipc_denied_when_caller_not_in_allowed(self):
        supervisor = self._make_supervisor(enforce_ipc=True)
        handler = self._make_handler(allowed_callers=["crm"])

        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

        loader = MagicMock()
        loader.get.return_value = handler
        loader.has.return_value = True
        loader.get_manifest.return_value = handler.manifest
        supervisor._loader = loader

        supervisor._pipeline = MiddlewarePipeline([], supervisor._dispatch)
        supervisor._pipeline.add_middleware(
            IPCAuthMiddleware(loader, enforce=True), first=True
        )

        result = await supervisor.call("inventory", "get", {}, caller="billing")
        assert result["status"] == "error"
        assert result["code"] == "ipc_denied"

    @pytest.mark.asyncio
    async def test_ipc_allowed_when_caller_in_list(self):
        supervisor = self._make_supervisor(enforce_ipc=True)
        handler = self._make_handler(allowed_callers=["billing", "crm"])

        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

        loader = MagicMock()
        loader.get.return_value = handler
        loader.has.return_value = True
        loader.get_manifest.return_value = handler.manifest
        supervisor._loader = loader

        # Patch _dispatch pour ne pas exploser sur le wrapping services
        supervisor._dispatch = AsyncMock(return_value={"status": "ok"})
        supervisor._pipeline = MiddlewarePipeline([], supervisor._dispatch)
        supervisor._pipeline.add_middleware(
            IPCAuthMiddleware(loader, enforce=True), first=True
        )

        result = await supervisor.call("inventory", "get", {}, caller="billing")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_http_direct_call_always_passes(self):
        supervisor = self._make_supervisor(enforce_ipc=True)
        handler = self._make_handler(allowed_callers=[])  # deny-by-default

        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

        loader = MagicMock()
        loader.get.return_value = handler
        loader.has.return_value = True
        loader.get_manifest.return_value = handler.manifest
        supervisor._loader = loader

        supervisor._dispatch = AsyncMock(return_value={"status": "ok"})
        supervisor._pipeline = MiddlewarePipeline([], supervisor._dispatch)
        supervisor._pipeline.add_middleware(
            IPCAuthMiddleware(loader, enforce=True), first=True
        )

        # caller=None → HTTP direct
        result = await supervisor.call("inventory", "get", {}, caller=None)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_enforce_ipc_false_allows_all(self):
        supervisor = self._make_supervisor(enforce_ipc=False)
        handler = self._make_handler(allowed_callers=[])  # liste vide

        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

        loader = MagicMock()
        loader.get.return_value = handler
        loader.has.return_value = True
        loader.get_manifest.return_value = handler.manifest
        supervisor._loader = loader

        supervisor._dispatch = AsyncMock(return_value={"status": "ok"})
        supervisor._pipeline = MiddlewarePipeline([], supervisor._dispatch)
        supervisor._pipeline.add_middleware(
            IPCAuthMiddleware(loader, enforce=False), first=True
        )

        result = await supervisor.call("inventory", "get", {}, caller="anyone")
        assert result["status"] == "ok"


# ─────────────────────────────────────────────────────────────
# Propagation tenant_id dans wrap_services_for_tenant
# ─────────────────────────────────────────────────────────────


class TestTenantPropagation:
    @pytest.mark.asyncio
    async def test_tenant_id_propagated_to_wrapped_cache(self, in_memory_cache):
        from xcore.kernel.tenancy.services import (
            TenantAwareCache,
            wrap_services_for_tenant,
        )

        services = {"cache": in_memory_cache, "db": None}
        wrapped = wrap_services_for_tenant(
            services, "acme", isolate_cache=True, isolate_db=False
        )
        cache = wrapped["cache"]
        assert isinstance(cache, TenantAwareCache)
        assert cache._tenant == "acme"

        await cache.set("x", 42)
        assert in_memory_cache._store.get("acme:x") == 42

    @pytest.mark.asyncio
    async def test_different_tenant_ids_produce_different_keys(self, in_memory_cache):
        from xcore.kernel.tenancy.services import wrap_services_for_tenant

        wrapped_a = wrap_services_for_tenant(
            {"cache": in_memory_cache}, "acme", isolate_cache=True, isolate_db=False
        )
        wrapped_b = wrap_services_for_tenant(
            {"cache": in_memory_cache}, "beta", isolate_cache=True, isolate_db=False
        )

        await wrapped_a["cache"].set("data", "from_acme")
        await wrapped_b["cache"].set("data", "from_beta")

        store = in_memory_cache._store
        assert store["acme:data"] == "from_acme"
        assert store["beta:data"] == "from_beta"

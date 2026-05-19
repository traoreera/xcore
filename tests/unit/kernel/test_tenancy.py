"""
tests/unit/kernel/test_tenancy.py — Tests unitaires du système multi-tenant.

Couvre :
  - TenantAwareCache  : préfixage des clés, toutes les méthodes
  - TenantAwareDB     : search_path, context manager session()
  - TenantAwareScheduler : préfixage job_id, filtrage get_jobs()
  - wrap_services_for_tenant() : flags isolate_*, détection adapters DB
  - IPCAuthMiddleware : allow / deny / HTTP direct / enforce=False
  - TenantMiddleware  : header, sous-domaine, fallback, disabled
  - TenancyConfig     : parsing depuis dict
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ─────────────────────────────────────────────────────────────
# TenantAwareCache
# ─────────────────────────────────────────────────────────────


class TestTenantAwareCache:
    def _make(self, tenant="acme"):
        from xcore.kernel.tenancy.services import TenantAwareCache

        backend = MagicMock()
        backend.get = AsyncMock(return_value="val")
        backend.set = AsyncMock()
        backend.delete = AsyncMock()
        backend.exists = AsyncMock(return_value=True)
        backend.incr = AsyncMock(return_value=5)
        backend.keys = AsyncMock(return_value=["acme:a", "acme:b"])
        return TenantAwareCache(backend, tenant), backend

    @pytest.mark.asyncio
    async def test_get_prefixes_key(self):
        cache, backend = self._make()
        await cache.get("invoices")
        backend.get.assert_called_once_with("acme:invoices", None)

    @pytest.mark.asyncio
    async def test_set_prefixes_key(self):
        cache, backend = self._make()
        await cache.set("orders", [1, 2, 3], ttl=60)
        backend.set.assert_called_once_with("acme:orders", [1, 2, 3], ttl=60)

    @pytest.mark.asyncio
    async def test_delete_prefixes_key(self):
        cache, backend = self._make()
        await cache.delete("orders")
        backend.delete.assert_called_once_with("acme:orders")

    @pytest.mark.asyncio
    async def test_exists_prefixes_key(self):
        cache, backend = self._make()
        result = await cache.exists("orders")
        backend.exists.assert_called_once_with("acme:orders")
        assert result is True

    @pytest.mark.asyncio
    async def test_incr_prefixes_key(self):
        cache, backend = self._make()
        result = await cache.incr("counter", 3)
        backend.incr.assert_called_once_with("acme:counter", 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_keys_strips_prefix(self):
        cache, backend = self._make()
        keys = await cache.keys("*")
        backend.keys.assert_called_once_with("acme:*")
        assert keys == ["a", "b"]

    @pytest.mark.asyncio
    async def test_clear_deletes_matching_keys(self):
        cache, backend = self._make()
        backend.keys = AsyncMock(return_value=["acme:x", "acme:y"])
        backend.delete = AsyncMock()
        count = await cache.clear("*")
        assert count == 2
        assert backend.delete.call_count == 2

    def test_unknown_attrs_delegated_to_backend(self):
        from xcore.kernel.tenancy.services import TenantAwareCache

        class FakeBackend:
            pipeline = "pipe"

        cache = TenantAwareCache(FakeBackend(), "acme")
        assert cache.pipeline == "pipe"

    def test_different_tenants_have_different_prefixes(self):
        from xcore.kernel.tenancy.services import TenantAwareCache

        backend = MagicMock()
        cache_a = TenantAwareCache(backend, "acme")
        cache_b = TenantAwareCache(backend, "beta")
        assert cache_a._k("x") == "acme:x"
        assert cache_b._k("x") == "beta:x"


# ─────────────────────────────────────────────────────────────
# TenantAwareDB
# ─────────────────────────────────────────────────────────────


class TestTenantAwareDB:
    def _make(self, tenant="acme"):
        import contextlib

        from xcore.kernel.tenancy.services import TenantAwareDB

        sess = MagicMock()
        sess.execute = AsyncMock(return_value="result")
        sess.fetch_one = AsyncMock(return_value={"id": 1})
        sess.fetch_all = AsyncMock(return_value=[{"id": 1}])

        @contextlib.asynccontextmanager
        async def fake_session():
            yield sess

        db = MagicMock()
        db.session = fake_session
        return TenantAwareDB(db, tenant), db, sess

    @pytest.mark.asyncio
    async def test_execute_sets_search_path(self):
        tdb, _, sess = self._make()
        await tdb.execute("SELECT 1")
        # first call = SET search_path, second = actual query
        calls = [c.args[0] for c in sess.execute.call_args_list]
        assert any("SET search_path TO acme" in str(c) for c in calls)
        assert any("SELECT 1" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        tdb, _, sess = self._make()
        async with tdb.session() as s:
            assert s is sess
        # SET search_path appelé pendant la session
        sess.execute.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_one_sets_search_path(self):
        tdb, _, sess = self._make()
        result = await tdb.fetch_one("SELECT * FROM users WHERE id=1")
        calls = [c.args[0] for c in sess.execute.call_args_list]
        assert any("SET search_path TO acme" in str(c) for c in calls)
        assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_fetch_all_sets_search_path(self):
        tdb, _, sess = self._make()
        result = await tdb.fetch_all("SELECT * FROM users")
        assert result == [{"id": 1}]

    def test_unknown_attrs_delegated_to_db(self):
        tdb, db, _ = self._make()
        db.engine = "pg-engine"
        assert tdb.engine == "pg-engine"

    @pytest.mark.asyncio
    async def test_non_postgres_silences_search_path_error(self):
        import contextlib

        from xcore.kernel.tenancy.services import TenantAwareDB

        sess = MagicMock()
        # search_path raises (SQLite/MySQL) — must not propagate
        sess.execute = AsyncMock(side_effect=[Exception("no search_path"), "result"])

        @contextlib.asynccontextmanager
        async def fake_session():
            yield sess

        db = MagicMock()
        db.session = fake_session

        tdb = TenantAwareDB(db, "acme")
        # Should not raise
        await tdb.execute("SELECT 1")


# ─────────────────────────────────────────────────────────────
# TenantAwareScheduler
# ─────────────────────────────────────────────────────────────


class TestTenantAwareScheduler:
    def _make(self, tenant="acme"):
        from xcore.kernel.tenancy.services import TenantAwareScheduler

        backend = MagicMock()
        return TenantAwareScheduler(backend, tenant), backend

    def test_add_job_prefixes_id(self):
        sched, backend = self._make()
        sched.add_job(lambda: None, id="cleanup")
        backend.add_job.assert_called_once()
        assert backend.add_job.call_args.kwargs.get("id") == "acme:cleanup"

    def test_add_job_without_id_passes_through(self):
        sched, backend = self._make()

        def fn():
            return None

        sched.add_job(fn)
        backend.add_job.assert_called_once_with(fn)

    def test_remove_job_prefixes_id(self):
        sched, backend = self._make()
        sched.remove_job("cleanup")
        backend.remove_job.assert_called_once_with("acme:cleanup")

    def test_get_job_prefixes_id(self):
        sched, backend = self._make()
        sched.get_job("cleanup")
        backend.get_job.assert_called_once_with("acme:cleanup")

    def test_pause_resume_job_prefix(self):
        sched, backend = self._make()
        sched.pause_job("myjob")
        sched.resume_job("myjob")
        backend.pause_job.assert_called_once_with("acme:myjob")
        backend.resume_job.assert_called_once_with("acme:myjob")

    def test_get_jobs_filters_by_tenant(self):
        sched, backend = self._make("acme")
        job_acme = MagicMock(id="acme:cleanup")
        job_beta = MagicMock(id="beta:cleanup")
        job_other = MagicMock(id="no_tenant")
        backend.get_jobs.return_value = [job_acme, job_beta, job_other]
        result = sched.get_jobs()
        assert result == [job_acme]

    def test_unknown_attrs_delegated(self):
        from xcore.kernel.tenancy.services import TenantAwareScheduler

        class FakeScheduler:
            timezone = "Europe/Paris"

        sched = TenantAwareScheduler(FakeScheduler(), "acme")
        assert sched.timezone == "Europe/Paris"


# ─────────────────────────────────────────────────────────────
# wrap_services_for_tenant
# ─────────────────────────────────────────────────────────────


class TestWrapServicesForTenant:
    def _make_services(self):
        cache = MagicMock()
        db = MagicMock()
        scheduler = MagicMock()
        worker = MagicMock()
        return {"cache": cache, "db": db, "scheduler": scheduler, "worker": worker}

    def test_wraps_cache_when_isolate_cache(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareCache,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=True, isolate_db=False
        )
        assert isinstance(result["cache"], TenantAwareCache)
        assert result["cache"]._tenant == "acme"

    def test_no_cache_wrap_when_disabled(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareCache,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=False
        )
        assert not isinstance(result["cache"], TenantAwareCache)

    def test_wraps_db_when_isolate_db(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareDB,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=True
        )
        assert isinstance(result["db"], TenantAwareDB)
        assert result["db"]._tenant == "acme"

    def test_no_db_wrap_when_disabled(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareDB,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=False
        )
        assert not isinstance(result["db"], TenantAwareDB)

    def test_wraps_scheduler_when_enabled(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareScheduler,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=False, isolate_scheduler=True
        )
        assert isinstance(result["scheduler"], TenantAwareScheduler)

    def test_no_scheduler_wrap_by_default(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareScheduler,
            wrap_services_for_tenant,
        )

        svcs = self._make_services()
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=False
        )
        assert not isinstance(result["scheduler"], TenantAwareScheduler)

    def test_worker_never_wrapped(self):
        from xcore.kernel.tenancy.services import wrap_services_for_tenant

        svcs = self._make_services()
        original_worker = svcs["worker"]
        result = wrap_services_for_tenant(svcs, "acme")
        assert result["worker"] is original_worker

    def test_named_db_adapters_also_wrapped(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareDB,
            wrap_services_for_tenant,
        )

        class FakeAsyncSQLAdapter:
            pass

        svcs = {
            "db": MagicMock(),
            "analytics": FakeAsyncSQLAdapter(),
            "cache": MagicMock(),
        }
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=False, isolate_db=True
        )
        assert isinstance(result["analytics"], TenantAwareDB)

    def test_original_dict_not_mutated(self):
        from xcore.kernel.tenancy.services import wrap_services_for_tenant

        svcs = self._make_services()
        original_cache = svcs["cache"]
        wrap_services_for_tenant(svcs, "acme")
        assert svcs["cache"] is original_cache  # pas de mutation in-place

    def test_none_cache_not_wrapped(self):
        from xcore.kernel.tenancy.services import (
            TenantAwareCache,
            wrap_services_for_tenant,
        )

        svcs = {"cache": None, "db": MagicMock()}
        result = wrap_services_for_tenant(
            svcs, "acme", isolate_cache=True, isolate_db=False
        )
        assert result["cache"] is None


# ─────────────────────────────────────────────────────────────
# IPCAuthMiddleware
# ─────────────────────────────────────────────────────────────


class TestIPCAuthMiddleware:
    def _make_loader(self, allowed_callers):
        manifest = MagicMock()
        manifest.allowed_callers = allowed_callers
        loader = MagicMock()
        loader.get_manifest.return_value = manifest
        return loader

    async def _call(self, mw, caller, plugin="target"):
        next_fn = AsyncMock(return_value={"status": "ok"})
        result = await mw(
            plugin, "action", {}, next_fn, handler=MagicMock(), caller=caller
        )
        return result, next_fn

    @pytest.mark.asyncio
    async def test_http_direct_call_passes_through(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        from xcore.kernel.tenancy.services import wrap_services_for_tenant

        loader = self._make_loader([])
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, next_fn = await self._call(mw, caller=None)
        assert result == {"status": "ok"}
        next_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_enforce_false_allows_all_ipc(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = self._make_loader([])  # liste vide = deny normalement
        mw = IPCAuthMiddleware(loader, enforce=False)
        result, next_fn = await self._call(mw, caller="billing")
        assert result == {"status": "ok"}
        next_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_allowed_callers_denies(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = self._make_loader([])
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, next_fn = await self._call(mw, caller="billing")
        assert result["status"] == "error"
        assert result["code"] == "ipc_denied"
        next_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_caller_in_allowed_list_passes(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = self._make_loader(["billing", "crm"])
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, next_fn = await self._call(mw, caller="billing")
        assert result == {"status": "ok"}
        next_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_caller_not_in_allowed_list_denied(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = self._make_loader(["crm"])
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, next_fn = await self._call(mw, caller="billing")
        assert result["status"] == "error"
        assert result["code"] == "ipc_denied"
        next_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_manifest_not_found_denies(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = MagicMock()
        loader.get_manifest.return_value = None
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, next_fn = await self._call(mw, caller="billing")
        assert result["status"] == "error"
        assert result["code"] == "ipc_denied"

    @pytest.mark.asyncio
    async def test_deny_message_contains_plugin_names(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        loader = self._make_loader(["crm"])
        mw = IPCAuthMiddleware(loader, enforce=True)
        result, _ = await self._call(mw, caller="billing", plugin="inventory")
        assert "billing" in result["msg"]
        assert "inventory" in result["msg"]


# ─────────────────────────────────────────────────────────────
# TenantMiddleware
# ─────────────────────────────────────────────────────────────


class TestTenantMiddleware:
    def _make_config(self, **kwargs):
        from xcore.configurations.sections import TenancyConfig

        return TenancyConfig(**kwargs)

    def _make_scope(self, headers=None, host="app.example.com"):
        return {
            "type": "http",
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
            ],
            "server": (host, 80),
        }

    @pytest.mark.asyncio
    async def test_header_extraction(self):
        from xcore.kernel.tenancy.middleware import TenantMiddleware

        config = self._make_config(
            enabled=True, header="X-Tenant-ID", default_tenant="default"
        )
        injected = {}

        async def call_next(request):
            injected["tenant"] = request.state.tenant_id
            from starlette.responses import Response

            return Response()

        from starlette.requests import Request

        scope = self._make_scope(headers={"X-Tenant-ID": "acme"})
        scope["method"] = "GET"
        scope["path"] = "/"
        scope["query_string"] = b""
        scope["root_path"] = ""

        mw = TenantMiddleware(MagicMock(), config=config)
        request = Request(scope)
        await mw.dispatch(request, call_next)
        assert injected["tenant"] == "acme"

    @pytest.mark.asyncio
    async def test_fallback_to_default_tenant(self):
        from xcore.kernel.tenancy.middleware import TenantMiddleware

        config = self._make_config(
            enabled=True, header="X-Tenant-ID", default_tenant="public"
        )
        injected = {}

        async def call_next(request):
            injected["tenant"] = request.state.tenant_id
            from starlette.responses import Response

            return Response()

        from starlette.requests import Request

        scope = self._make_scope(headers={})  # no tenant header
        scope["method"] = "GET"
        scope["path"] = "/"
        scope["query_string"] = b""
        scope["root_path"] = ""

        mw = TenantMiddleware(MagicMock(), config=config)
        request = Request(scope)
        await mw.dispatch(request, call_next)
        assert injected["tenant"] == "public"

    @pytest.mark.asyncio
    async def test_disabled_injects_default_tenant(self):
        from xcore.kernel.tenancy.middleware import TenantMiddleware

        config = self._make_config(enabled=False, default_tenant="default")
        injected = {}

        async def call_next(request):
            injected["tenant"] = request.state.tenant_id
            from starlette.responses import Response

            return Response()

        from starlette.requests import Request

        scope = self._make_scope(headers={"X-Tenant-ID": "acme"})
        scope["method"] = "GET"
        scope["path"] = "/"
        scope["query_string"] = b""
        scope["root_path"] = ""

        mw = TenantMiddleware(MagicMock(), config=config)
        request = Request(scope)
        await mw.dispatch(request, call_next)
        # disabled → ignore header, inject default
        assert injected["tenant"] == "default"

    @pytest.mark.asyncio
    async def test_subdomain_extraction(self):
        from xcore.kernel.tenancy.middleware import TenantMiddleware

        config = self._make_config(
            enabled=True,
            header="X-Tenant-ID",
            subdomain=True,
            default_tenant="default",
        )
        injected = {}

        async def call_next(request):
            injected["tenant"] = request.state.tenant_id
            from starlette.responses import Response

            return Response()

        from starlette.requests import Request

        scope = self._make_scope(
            headers={"host": "beta.example.com"}, host="beta.example.com"
        )
        scope["method"] = "GET"
        scope["path"] = "/"
        scope["query_string"] = b""
        scope["root_path"] = ""

        mw = TenantMiddleware(MagicMock(), config=config)
        request = Request(scope)
        await mw.dispatch(request, call_next)
        assert injected["tenant"] == "beta"


# ─────────────────────────────────────────────────────────────
# TenancyConfig parsing
# ─────────────────────────────────────────────────────────────


class TestTenancyConfigParsing:
    def test_defaults(self):
        from xcore.configurations.sections import TenancyConfig

        cfg = TenancyConfig()
        assert cfg.enabled is False
        assert cfg.header == "X-Tenant-ID"
        assert cfg.subdomain is False
        assert cfg.default_tenant == "default"
        assert cfg.isolate_cache is True
        assert cfg.isolate_db is True
        assert cfg.isolate_scheduler is False
        assert cfg.enforce_ipc is True

    def test_parse_from_loader(self):
        from xcore.configurations.loader import ConfigLoader

        raw = {
            "tenancy": {
                "enabled": True,
                "header": "X-App-Tenant",
                "subdomain": True,
                "default_tenant": "global",
                "isolate_cache": False,
                "isolate_db": True,
                "isolate_scheduler": True,
                "enforce_ipc": False,
            }
        }
        cfg = ConfigLoader._parse_tenancy(raw["tenancy"])
        assert cfg.enabled is True
        assert cfg.header == "X-App-Tenant"
        assert cfg.subdomain is True
        assert cfg.default_tenant == "global"
        assert cfg.isolate_cache is False
        assert cfg.isolate_scheduler is True
        assert cfg.enforce_ipc is False

    def test_partial_config_uses_defaults(self):
        from xcore.configurations.loader import ConfigLoader

        cfg = ConfigLoader._parse_tenancy({"enabled": True})
        assert cfg.enabled is True
        assert cfg.header == "X-Tenant-ID"
        assert cfg.isolate_cache is True

"""
tests/benchmarks/test_tenancy_bench.py — Benchmarks pytest du système multi-tenant.

Suites :
  - TenantAwareCache set/get overhead vs backend brut
  - IPCAuthMiddleware : allowed / denied / HTTP direct / enforce=False
  - wrap_services_for_tenant() : coût d'instanciation des wrappers
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def memory_backend():
    from xcore.services.cache.backends.memory import MemoryBackend

    return MemoryBackend(ttl=300, max_size=100_000)


@pytest.fixture
def tenant_cache(memory_backend):
    from xcore.kernel.tenancy.services import TenantAwareCache

    return TenantAwareCache(memory_backend, "acme")


@pytest.fixture
def ipc_mw_allow():
    from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

    manifest = MagicMock()
    manifest.allowed_callers = ["billing"]
    loader = MagicMock()
    loader.get_manifest.return_value = manifest
    return IPCAuthMiddleware(loader, enforce=True)


@pytest.fixture
def ipc_mw_deny():
    from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

    manifest = MagicMock()
    manifest.allowed_callers = []
    loader = MagicMock()
    loader.get_manifest.return_value = manifest
    return IPCAuthMiddleware(loader, enforce=True)


@pytest.fixture
def ipc_mw_off():
    from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

    manifest = MagicMock()
    manifest.allowed_callers = []
    loader = MagicMock()
    loader.get_manifest.return_value = manifest
    return IPCAuthMiddleware(loader, enforce=False)


@pytest.fixture
def next_ok():
    return AsyncMock(return_value={"status": "ok"})


# ─────────────────────────────────────────────────────────────
# TenantAwareCache — overhead de préfixage
# ─────────────────────────────────────────────────────────────


@pytest.mark.benchmark(group="tenant-cache")
def test_cache_set_raw(benchmark, memory_backend):
    """SET brut sur le backend sans wrapper."""

    async def _set():
        await memory_backend.set("acme:key:1", {"v": 1})

    benchmark(
        lambda: pytest.importorskip("asyncio")
        .get_event_loop()
        .run_until_complete(_set())
    )


@pytest.mark.benchmark(group="tenant-cache")
def test_cache_set_wrapped(benchmark, tenant_cache):
    """SET via TenantAwareCache (préfixage inclus)."""

    async def _set():
        await tenant_cache.set("key:1", {"v": 1})

    benchmark(
        lambda: pytest.importorskip("asyncio")
        .get_event_loop()
        .run_until_complete(_set())
    )


@pytest.mark.benchmark(group="tenant-cache")
def test_cache_get_raw(benchmark, memory_backend):
    """GET brut — lecture clé déjà préfixée."""
    import asyncio

    asyncio.get_event_loop().run_until_complete(
        memory_backend.set("acme:key:1", {"v": 1})
    )

    async def _get():
        return await memory_backend.get("acme:key:1")

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_get()))


@pytest.mark.benchmark(group="tenant-cache")
def test_cache_get_wrapped(benchmark, tenant_cache):
    """GET via TenantAwareCache."""
    import asyncio

    asyncio.get_event_loop().run_until_complete(tenant_cache.set("key:1", {"v": 1}))

    async def _get():
        return await tenant_cache.get("key:1")

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_get()))


# ─────────────────────────────────────────────────────────────
# IPCAuthMiddleware — latence selon le scénario
# ─────────────────────────────────────────────────────────────


@pytest.mark.benchmark(group="ipc-auth")
def test_ipc_http_direct(benchmark, ipc_mw_deny, next_ok):
    """HTTP direct (caller=None) — fast path, pas de vérification."""
    import asyncio

    async def _call():
        return await ipc_mw_deny(
            "target", "act", {}, next_ok, handler=MagicMock(), caller=None
        )

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_call()))


@pytest.mark.benchmark(group="ipc-auth")
def test_ipc_caller_allowed(benchmark, ipc_mw_allow, next_ok):
    """IPC autorisé — caller dans allowed_callers."""
    import asyncio

    async def _call():
        return await ipc_mw_allow(
            "target", "act", {}, next_ok, handler=MagicMock(), caller="billing"
        )

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_call()))


@pytest.mark.benchmark(group="ipc-auth")
def test_ipc_caller_denied(benchmark, ipc_mw_deny, next_ok):
    """IPC refusé — deny-by-default (liste vide)."""
    import asyncio

    async def _call():
        return await ipc_mw_deny(
            "target", "act", {}, next_ok, handler=MagicMock(), caller="intruder"
        )

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_call()))


@pytest.mark.benchmark(group="ipc-auth")
def test_ipc_enforce_off(benchmark, ipc_mw_off, next_ok):
    """IPC avec enforce=False — bypass complet."""
    import asyncio

    async def _call():
        return await ipc_mw_off(
            "target", "act", {}, next_ok, handler=MagicMock(), caller="anyone"
        )

    benchmark(lambda: asyncio.get_event_loop().run_until_complete(_call()))


# ─────────────────────────────────────────────────────────────
# wrap_services_for_tenant — coût d'instanciation
# ─────────────────────────────────────────────────────────────


@pytest.mark.benchmark(group="wrap-services")
def test_wrap_services_cache_only(benchmark, memory_backend):
    """Coût de wrap_services_for_tenant() avec isolate_cache=True."""
    from xcore.kernel.tenancy.services import wrap_services_for_tenant

    services = {"cache": memory_backend, "db": None}

    benchmark(
        lambda: wrap_services_for_tenant(
            services, "acme", isolate_cache=True, isolate_db=False
        )
    )


@pytest.mark.benchmark(group="wrap-services")
def test_wrap_services_all(benchmark, memory_backend):
    """Coût de wrap_services_for_tenant() avec toutes les isolations actives."""
    from xcore.kernel.tenancy.services import wrap_services_for_tenant

    services = {"cache": memory_backend, "db": None, "scheduler": MagicMock()}

    benchmark(
        lambda: wrap_services_for_tenant(
            services,
            "acme",
            isolate_cache=True,
            isolate_db=False,
            isolate_scheduler=True,
        )
    )


@pytest.mark.benchmark(group="wrap-services")
def test_wrap_services_10_tenants(benchmark, memory_backend):
    """Rotation sur 10 tenants différents — simule un serveur multi-tenant actif."""
    from xcore.kernel.tenancy.services import wrap_services_for_tenant

    services = {"cache": memory_backend, "db": None}
    tenants = [f"tenant_{i}" for i in range(10)]

    def _rotate():
        for t in tenants:
            wrap_services_for_tenant(services, t, isolate_cache=True, isolate_db=False)

    benchmark(_rotate)

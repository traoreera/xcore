"""Tests for API middlewares: Middlewares loader, RBAC, CacheHeader, Timing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import Response
from starlette.testclient import TestClient as StarletteClient


# ── CacheHeaderMiddleware ─────────────────────────────────────────────────────

class TestCacheHeaderMiddleware:
    def _make_app(self, **kwargs):
        from xcore.kernel.api.middlewares.cache_header import CacheHeaderMiddleware
        app = FastAPI()
        app.add_middleware(CacheHeaderMiddleware, **kwargs)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        return app

    def test_adds_process_time_header(self):
        app = self._make_app(header_prefix="X-Test")
        client = TestClient(app)
        resp = client.get("/ping")
        assert "X-Test-Process-Time" in resp.headers

    def test_default_prefix(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/ping")
        assert "X-App-Process-Time" in resp.headers

    def test_cache_getter_called(self):
        mock_cache = MagicMock()
        mock_cache._config = MagicMock()
        mock_cache._config.backend = "memory"
        cache_getter = MagicMock(return_value=mock_cache)
        app = self._make_app(cache_getter=cache_getter)
        client = TestClient(app)
        resp = client.get("/ping")
        assert "X-App-Cache-Backend" in resp.headers
        assert resp.headers["X-App-Cache-Backend"] == "memory"

    def test_cache_getter_exception(self):
        def bad_getter():
            raise RuntimeError("boom")
        app = self._make_app(cache_getter=bad_getter)
        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.headers.get("X-App-Cache-Backend") == "unavailable"

    def test_no_cache_getter(self):
        app = self._make_app(cache_getter=None)
        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "X-App-Cache-Backend" not in resp.headers


# ── RequestTimingMiddleware ───────────────────────────────────────────────────

class TestRequestTimingMiddleware:
    def test_adds_x_process_time(self):
        from xcore.kernel.api.middlewares.timing import RequestTimingMiddleware
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert "X-Process-Time" in resp.headers
        assert "ms" in resp.headers["X-Process-Time"]


# ── Middlewares (api/middleware.py) ───────────────────────────────────────────

class TestMiddlewaresLoader:
    def _config(self, name, module, params=None):
        from xcore.configurations.sections import MiddlewareConfig, MiddlewareParam

        param_objs = []
        for p in (params or []):
            param_objs.append(MiddlewareParam(**p))
        return MiddlewareConfig(name=name, module=module, config=param_objs)

    def test_configure_no_config(self):
        from xcore.kernel.api.middleware import Middlewares
        m = Middlewares([], prototypes=MagicMock(), event_bus=MagicMock())
        app = FastAPI()
        logger = MagicMock()
        m.configure(app, logger)  # should not raise

    def test_configure_none_app(self):
        from xcore.kernel.api.middleware import Middlewares
        m = Middlewares([], prototypes=MagicMock(), event_bus=MagicMock())
        m.configure(None, MagicMock())  # should not raise

    def test_configure_module_no_module_field(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig
        cfg = MiddlewareConfig(name="test", module="", config=[])
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=MagicMock())
        logger = MagicMock()
        m.configure(FastAPI(), logger)
        logger.warning.assert_called()

    def test_configure_invalid_module_format(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig
        cfg = MiddlewareConfig(name="test", module="no_colon", config=[])
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=MagicMock())
        logger = MagicMock()
        m.configure(FastAPI(), logger)
        logger.warning.assert_called()

    def test_configure_import_error(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig
        cfg = MiddlewareConfig(name="test", module="nonexistent.module:SomeClass", config=[])
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=MagicMock())
        logger = MagicMock()
        m.configure(FastAPI(), logger)
        logger.error.assert_called()

    def test_configure_with_timing_middleware(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig
        cfg = MiddlewareConfig(
            name="timing",
            module="xcore.kernel.api.middlewares.timing:RequestTimingMiddleware",
            config=[],
        )
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=MagicMock())
        app = FastAPI()
        logger = MagicMock()
        m.configure(app, logger)
        logger.info.assert_called()

    def test_configure_external_param(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig, MiddleParams
        param = MiddleParams(name="header_prefix", type="external", value="X-Custom")
        cfg = MiddlewareConfig(
            name="cache_header",
            module="xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware",
            config=[param],
        )
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=MagicMock())
        app = FastAPI()
        logger = MagicMock()
        m.configure(app, logger)
        logger.info.assert_called()

    def test_configure_internal_param(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig, MiddleParams
        param = MiddleParams(name="cache_getter", type="internal", value="cache")
        cfg = MiddlewareConfig(
            name="cache_header",
            module="xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware",
            config=[param],
        )
        prototypes = MagicMock()
        m = Middlewares([cfg], prototypes=prototypes, event_bus=MagicMock())
        app = FastAPI()
        logger = MagicMock()
        m.configure(app, logger)
        logger.info.assert_called()

    def test_configure_events_param(self):
        from xcore.kernel.api.middleware import Middlewares
        from xcore.configurations.sections import MiddlewareConfig, MiddleParams
        param = MiddleParams(name="cache_getter", type="events", value="bus")
        cfg = MiddlewareConfig(
            name="cache_header",
            module="xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware",
            config=[param],
        )
        event_bus = MagicMock()
        m = Middlewares([cfg], prototypes=MagicMock(), event_bus=event_bus)
        app = FastAPI()
        logger = MagicMock()
        m.configure(app, logger)
        logger.info.assert_called()


# ── RBAC ──────────────────────────────────────────────────────────────────────

class TestRBAC:
    @pytest.mark.asyncio
    async def test_get_user_session_id_missing_sub(self):
        from xcore.kernel.api.rbac import get_user_session_id
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_user_session_id(user={})
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_session_id_with_sub(self):
        from xcore.kernel.api.rbac import get_user_session_id

        result = await get_user_session_id(user={"sub": "user-123"})
        assert result == "user-123"

    def test_require_role_creates_rbac_checker(self):
        from xcore.kernel.api.rbac import require_role, RBACChecker
        checker = require_role("admin", "moderator")
        assert isinstance(checker, RBACChecker)
        assert checker._required == {"admin", "moderator"}

    def test_require_permission_creates_rbac_checker(self):
        from xcore.kernel.api.rbac import require_permission, RBACChecker
        checker = require_permission("read:users")
        assert isinstance(checker, RBACChecker)

    @pytest.mark.asyncio
    async def test_rbac_checker_no_backend_strict(self):
        from xcore.kernel.api.rbac import RBACChecker
        from fastapi import HTTPException

        checker = RBACChecker(["admin"], strict=True)
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = None
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await checker(request, credentials=None)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_rbac_checker_no_backend_permissive(self):
        from xcore.kernel.api.rbac import RBACChecker

        checker = RBACChecker([], strict=False)
        request = MagicMock()
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=None):
            result = await checker(request, credentials=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_rbac_checker_with_backend_missing_permissions(self):
        from xcore.kernel.api.rbac import RBACChecker
        from fastapi import HTTPException

        checker = RBACChecker(["admin"])
        request = MagicMock()
        request.state.user = {"sub": "u1", "roles": ["user"], "permissions": []}
        backend = MagicMock()
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=backend):
            with patch("xcore.kernel.api.rbac._resolve_user", AsyncMock(return_value={"sub": "u1", "roles": ["user"], "permissions": []})):
                with pytest.raises(HTTPException) as exc_info:
                    await checker(request, credentials=None)
                assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rbac_checker_with_backend_has_permission(self):
        from xcore.kernel.api.rbac import RBACChecker

        checker = RBACChecker(["admin"])
        request = MagicMock()
        backend = MagicMock()
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=backend):
            with patch(
                "xcore.kernel.api.rbac._resolve_user",
                AsyncMock(return_value={"sub": "u1", "roles": ["admin"], "permissions": []}),
            ):
                result = await checker(request, credentials=None)
        assert result["sub"] == "u1"


class TestResolveUser:
    @pytest.mark.asyncio
    async def test_resolve_user_from_cache(self):
        from xcore.kernel.api.rbac import _resolve_user
        request = MagicMock()
        cached_user = {"sub": "cached-user"}
        request.state.user = cached_user
        result = await _resolve_user(request)
        assert result == cached_user

    @pytest.mark.asyncio
    async def test_resolve_user_no_backend(self):
        from xcore.kernel.api.rbac import _resolve_user
        from fastapi import HTTPException
        request = MagicMock()
        request.state.user = None
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await _resolve_user(request)
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_resolve_user_no_token(self):
        from xcore.kernel.api.rbac import _resolve_user
        from fastapi import HTTPException
        request = MagicMock()
        request.state.user = None
        backend = AsyncMock()
        backend.extract_token = AsyncMock(return_value=None)
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=backend):
            with pytest.raises(HTTPException) as exc:
                await _resolve_user(request)
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_user_invalid_token(self):
        from xcore.kernel.api.rbac import _resolve_user
        from fastapi import HTTPException
        request = MagicMock()
        request.state.user = None
        backend = AsyncMock()
        backend.extract_token = AsyncMock(return_value="bad_token")
        backend.decode_token = AsyncMock(return_value=None)
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=backend):
            with pytest.raises(HTTPException) as exc:
                await _resolve_user(request)
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_user_valid(self):
        from xcore.kernel.api.rbac import _resolve_user
        request = MagicMock()
        request.state.user = None
        backend = AsyncMock()
        backend.extract_token = AsyncMock(return_value="valid_token")
        backend.decode_token = AsyncMock(return_value={"sub": "user1", "roles": ["admin"]})
        with patch("xcore.kernel.api.rbac.get_auth_backend", return_value=backend):
            result = await _resolve_user(request)
        assert result["sub"] == "user1"
        assert request.state.user == result

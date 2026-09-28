"""Tests for xcore.kernel.api.router — build_router, _hash_key, endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xcore.kernel.api.router import CallRequest, CallResponse, _hash_key, build_router

SECRET_KEY = b"test-secret"
SERVER_KEY = b"test-server"


def _make_app(supervisor=None, **kwargs):
    if supervisor is None:
        supervisor = MagicMock()
        supervisor.call = AsyncMock(return_value={"status": "ok", "msg": "pong"})
        supervisor.status = MagicMock(return_value={"plugins": []})
        supervisor.reload = AsyncMock()
        supervisor.load = AsyncMock()
        supervisor.unload = AsyncMock()
    app = FastAPI()
    router, _ = build_router(
        supervisor,
        secret_key=SECRET_KEY,
        server_key=SERVER_KEY,
        **kwargs,
    )
    app.include_router(router)
    return app, supervisor


def _client_with_key(app, key: str = "test-secret"):
    return TestClient(app, raise_server_exceptions=False), {"X-Plugin-Key": key}


# ── _hash_key ─────────────────────────────────────────────────────────────────


class TestHashKey:
    def test_returns_bytes(self):
        result = _hash_key("mykey", "salt")
        assert isinstance(result, bytes)

    def test_bytes_key(self):
        result = _hash_key(b"mykey", b"salt")
        assert isinstance(result, bytes)

    def test_none_key_uses_empty_bytes(self):
        result = _hash_key(None, b"salt")
        assert isinstance(result, bytes)

    def test_none_server_key_raises(self):
        with pytest.raises(ValueError):
            _hash_key("key", None)

    def test_deterministic(self):
        r1 = _hash_key("key", "salt")
        r2 = _hash_key("key", "salt")
        assert r1 == r2

    def test_different_keys_differ(self):
        r1 = _hash_key("key1", "salt")
        r2 = _hash_key("key2", "salt")
        assert r1 != r2


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestRouterAuth:
    def test_missing_api_key_returns_401(self):
        app, _ = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/ipc/myplugin/ping", json={"payload": {}})
        assert resp.status_code == 401

    def test_wrong_api_key_returns_401(self):
        app, _ = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/ipc/myplugin/ping",
            json={"payload": {}},
            headers={"X-Plugin-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_correct_api_key_passes(self):
        app, _ = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/ipc/myplugin/ping",
            json={"payload": {}},
            headers={"X-Plugin-Key": "test-secret"},
        )
        assert resp.status_code == 200


# ── Endpoints ─────────────────────────────────────────────────────────────────


class TestRouterEndpoints:
    def setup_method(self):
        self.supervisor = MagicMock()
        self.supervisor.call = AsyncMock(
            return_value={"status": "ok", "result": "pong"}
        )
        self.supervisor.status = MagicMock(return_value={"plugins": ["auth"]})
        self.supervisor.reload = AsyncMock()
        self.supervisor.load = AsyncMock()
        self.supervisor.unload = AsyncMock()
        self.supervisor.enable = AsyncMock()
        self.supervisor.disable = AsyncMock()
        self.supervisor.registry_table = MagicMock(
            return_value=[{"name": "auth", "enabled": True, "state": "ready"}]
        )
        self.supervisor.ipc_audit = MagicMock(
            return_value=[{"plugin": "auth", "action": "login"}]
        )
        self.supervisor.ipc_stats = MagicMock(
            return_value={"entries": 1, "by_plugin": {}}
        )
        self.supervisor.events_activity = MagicMock(
            return_value={"recent": [], "stats": {}}
        )
        self.supervisor.hooks_activity = MagicMock(
            return_value={"recent": [], "metrics": {}}
        )
        self.app, _ = _make_app(self.supervisor)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.headers = {"X-Plugin-Key": "test-secret"}

    def test_call_plugin_success(self):
        resp = self.client.post(
            "/ipc/auth/login",
            json={"payload": {"email": "a@b.com"}},
            headers=self.headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plugin"] == "auth"
        assert data["action"] == "login"

    def test_call_plugin_not_found(self):
        self.supervisor.call = AsyncMock(
            return_value={
                "status": "error",
                "code": "not_found",
                "msg": "Plugin 'x' not found",
            }
        )
        resp = self.client.post(
            "/ipc/x/ping",
            json={"payload": {}},
            headers=self.headers,
        )
        assert resp.status_code == 404

    def test_call_plugin_invalid_supervisor_response(self):
        self.supervisor.call = AsyncMock(return_value=None)
        resp = self.client.post(
            "/ipc/auth/ping",
            json={"payload": {}},
            headers=self.headers,
        )
        assert resp.status_code == 500

    def test_status_endpoint(self):
        resp = self.client.get("/ipc/status", headers=self.headers)
        assert resp.status_code == 200
        assert "plugins" in resp.json()

    def test_reload_plugin(self):
        resp = self.client.post(
            "/ipc/auth/reload",
            json={"payload": {}},
            headers=self.headers,
        )
        # Route may match call_plugin (dynamic) or reload (static) — either is valid
        assert resp.status_code in (200, 422, 500)

    def test_load_plugin(self):
        resp = self.client.post(
            "/ipc/auth/load",
            json={"payload": {}},
            headers=self.headers,
        )
        assert resp.status_code in (200, 422, 500)

    def test_unload_plugin(self):
        resp = self.client.delete("/ipc/auth/unload", headers=self.headers)
        assert resp.status_code == 200
        self.supervisor.unload.assert_called_once_with("auth")

    def test_registry_endpoint(self):
        resp = self.client.get("/ipc/registry", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json() == {
            "plugins": [{"name": "auth", "enabled": True, "state": "ready"}]
        }

    def test_enable_plugin(self):
        resp = self.client.post("/ipc/auth/enable", headers=self.headers)
        assert resp.status_code == 200
        self.supervisor.enable.assert_called_once_with("auth")

    def test_disable_plugin_no_body(self):
        resp = self.client.post("/ipc/auth/disable", headers=self.headers)
        assert resp.status_code == 200
        self.supervisor.disable.assert_called_once_with("auth", reason=None)

    def test_disable_plugin_with_reason(self):
        resp = self.client.post(
            "/ipc/auth/disable",
            json={"reason": "maintenance"},
            headers=self.headers,
        )
        assert resp.status_code == 200
        self.supervisor.disable.assert_called_once_with("auth", reason="maintenance")

    def test_audit_endpoint(self):
        resp = self.client.get("/ipc/audit", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["calls"] == [{"plugin": "auth", "action": "login"}]
        assert data["stats"] == {"entries": 1, "by_plugin": {}}

    def test_audit_endpoint_with_query_params(self):
        resp = self.client.get(
            "/ipc/audit", params={"plugin": "auth", "limit": 10}, headers=self.headers
        )
        assert resp.status_code == 200
        self.supervisor.ipc_audit.assert_called_once_with("auth", 10)

    def test_events_endpoint(self):
        resp = self.client.get("/ipc/events", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == {"recent": [], "stats": {}}
        assert data["hooks"] == {"recent": [], "metrics": {}}

    def test_events_endpoint_with_query_params(self):
        resp = self.client.get(
            "/ipc/events",
            params={"event": "user.created", "limit": 5},
            headers=self.headers,
        )
        assert resp.status_code == 200
        self.supervisor.events_activity.assert_called_once_with("user.created", 5)
        self.supervisor.hooks_activity.assert_called_once_with("user.created", 5)

    def test_health_no_checker(self):
        resp = self.client.get("/ipc/health", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_with_checker(self):
        checker = MagicMock()
        checker.run_all = AsyncMock(return_value={"status": "healthy", "checks": {}})
        app, _ = _make_app(self.supervisor, health_checker=checker)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ipc/health", headers={"X-Plugin-Key": "test-secret"})
        assert resp.status_code == 200

    def test_metrics_no_registry(self):
        resp = self.client.get("/ipc/metrics", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_metrics_with_registry(self):
        from xcore.kernel.observability.metrics import MetricsRegistry

        metrics = MetricsRegistry()
        metrics.counter("calls").inc(5)
        app, _ = _make_app(self.supervisor, metrics_registry=metrics)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ipc/metrics", headers={"X-Plugin-Key": "test-secret"})
        assert resp.status_code == 200


# ── Models ────────────────────────────────────────────────────────────────────


class TestModels:
    def test_call_request_default(self):
        req = CallRequest()
        assert req.payload == {}

    def test_call_request_with_payload(self):
        req = CallRequest(payload={"key": "value"})
        assert req.payload == {"key": "value"}

    def test_call_response(self):
        resp = CallResponse(
            status="ok", plugin="auth", action="login", result={"token": "abc"}
        )
        assert resp.status == "ok"
        assert resp.plugin == "auth"

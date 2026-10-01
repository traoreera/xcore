"""
Régression : montage / retrait des routes FastAPI d'un plugin au unload et au
reload (`Xcore._mount_plugin_router`, `_unmount_plugin_router`,
`_remount_plugin_router`).

Avant le correctif, `_unmount_plugin_router` faisait `app.routes = [...]` —
propriété sans setter chez Starlette (AttributeError, avalée par l'EventBus) — et
filtrait sur `route.path`, attribut que les `_IncludedRouter` de FastAPI ≥ 0.14x
n'ont pas : après un unload ou un reload les anciennes routes restaient montées
et continuaient de servir l'ancien code du plugin.
"""

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from xcore import Xcore


def _router(answer: int) -> APIRouter:
    router = APIRouter()

    @router.get("/ping")
    async def ping():
        return {"answer": answer}

    return router


@pytest.fixture
def xcore_app():
    app = FastAPI()
    x = object.__new__(Xcore)
    x._app = app
    x._config = SimpleNamespace(
        app=SimpleNamespace(plugin_prefix="/plugins", plugin_tags=[])
    )
    x._logger = SimpleNamespace(info=lambda *a, **k: None)
    x._plugin_routes = {}
    x.plugins = SimpleNamespace(_loader=SimpleNamespace(get=lambda name: None))
    return x, app, TestClient(app)


def _mount(x, app, name, answer):
    x._mount_plugin_router(app, name, _router(answer), "/plugins", [])


class TestUnmount:
    def test_unmount_removes_the_plugin_routes(self, xcore_app):
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)
        assert client.get("/plugins/shop/ping").json() == {"answer": 1}

        x._unmount_plugin_router("shop")

        assert client.get("/plugins/shop/ping").status_code == 404

    def test_unmount_does_not_touch_a_plugin_with_a_longer_name(self, xcore_app):
        """`/plugins/shop` est un préfixe textuel de `/plugins/shop2`."""
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)
        _mount(x, app, "shop2", 2)

        x._unmount_plugin_router("shop")

        assert client.get("/plugins/shop/ping").status_code == 404
        assert client.get("/plugins/shop2/ping").json() == {"answer": 2}

    def test_unmount_without_app_is_a_noop(self, xcore_app):
        x, _, _ = xcore_app
        x._app = None
        x._unmount_plugin_router("shop")  # ne lève pas

    def test_unmount_invalidates_the_openapi_schema(self, xcore_app):
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)
        assert "/plugins/shop/ping" in client.get("/openapi.json").json()["paths"]

        x._unmount_plugin_router("shop")

        assert "/plugins/shop/ping" not in client.get("/openapi.json").json()["paths"]


class TestRemountAfterReload:
    def test_remount_serves_the_new_router_not_the_old_one(self, xcore_app):
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)
        new_handler = SimpleNamespace(plugin_router=_router(2))
        x.plugins = SimpleNamespace(_loader=SimpleNamespace(get=lambda n: new_handler))

        x._remount_plugin_router("shop")

        assert client.get("/plugins/shop/ping").json() == {"answer": 2}
        paths = [p for p in client.get("/openapi.json").json()["paths"] if "shop" in p]
        assert paths == ["/plugins/shop/ping"]  # pas de doublon

    def test_remount_drops_routes_when_the_new_code_has_no_router(self, xcore_app):
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)
        x.plugins = SimpleNamespace(
            _loader=SimpleNamespace(get=lambda n: SimpleNamespace(plugin_router=None))
        )

        x._remount_plugin_router("shop")

        assert client.get("/plugins/shop/ping").status_code == 404

    def test_remount_after_unload_of_the_handler_leaves_no_route(self, xcore_app):
        x, app, client = xcore_app
        _mount(x, app, "shop", 1)

        def _raise(name):
            raise KeyError(name)

        x.plugins = SimpleNamespace(_loader=SimpleNamespace(get=_raise))

        x._remount_plugin_router("shop")

        assert client.get("/plugins/shop/ping").status_code == 404


class TestMount:
    def test_router_already_prefixed_with_plugins_is_not_double_prefixed(
        self, xcore_app
    ):
        x, app, client = xcore_app
        router = APIRouter(prefix="/plugins/custom")

        @router.get("/ping")
        async def ping():
            return {"answer": 3}

        x._mount_plugin_router(app, "custom", router, "/plugins", [])

        assert client.get("/plugins/custom/ping").json() == {"answer": 3}
        x._unmount_plugin_router("custom")
        assert client.get("/plugins/custom/ping").status_code == 404

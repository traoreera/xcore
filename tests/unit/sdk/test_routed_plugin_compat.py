"""RouterIn() est un alias déprécié de get_router()."""

import warnings

import pytest

from xcore.kernel.api.contract import TrustedBase
from xcore.sdk.decorators import RoutedPlugin, route


class _Base(RoutedPlugin, TrustedBase):
    async def handle(self, action, payload):
        return {"status": "ok"}


class _Plain(_Base):
    @route("/ping", method="GET")
    async def ping(self):
        return {"pong": True}


class _LegacyOverride(_Base):
    """Pattern des plugins ERP : get_router() surchargé qui appelle RouterIn()."""

    @route("/ping", method="GET")
    async def ping(self):
        return {"pong": True}

    def get_router(self):
        return self.RouterIn()


def _paths(router):
    return {r.path for r in router.routes}


def test_router_in_warns_and_matches_get_router():
    plugin = _Plain()
    with pytest.warns(DeprecationWarning, match="get_router"):
        legacy = plugin.RouterIn()
    assert _paths(legacy) == _paths(plugin.get_router()) == {"/ping"}


def test_router_in_warning_points_to_caller():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _Plain().RouterIn()
    assert caught[0].filename == __file__


def test_legacy_override_does_not_recurse():
    with pytest.warns(DeprecationWarning):
        router = _LegacyOverride().get_router()
    assert _paths(router) == {"/ping"}


def test_get_router_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _paths(_Plain().get_router()) == {"/ping"}

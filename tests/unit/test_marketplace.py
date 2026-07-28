"""Tests for MarketplaceClient."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from xcore.marketplace.client import MarketplaceClient, MarketplaceError


def _make_client(tmp_path, **overrides):
    config = MagicMock()
    config.raw = {
        "marketplace": {
            "url": "https://marketplace.example.com",
            "api_key": "test-key",
            "timeout": 5,
            "cache_ttl": 60,
            **overrides,
        }
    }
    with patch("xcore.marketplace.client.CACHE_DIR", tmp_path):
        with patch.object(Path, "mkdir"):
            with patch.object(Path, "chmod"):
                client = MarketplaceClient.__new__(MarketplaceClient)
                client._base_url = "https://marketplace.example.com"
                client._api_key = overrides.get("api_key", "test-key")
                client._timeout = overrides.get("timeout", 5)
                client._cache_ttl = overrides.get("cache_ttl", 60)
                client._cache_dir = tmp_path
    return client


def _make_simple_client(tmp_path, api_key="test-key"):
    class _Cfg:
        raw = {"marketplace": {"url": "https://mp.example.com", "api_key": api_key, "timeout": 5, "cache_ttl": 60}}

    with patch.object(Path, "mkdir"):
        with patch.object(Path, "chmod"):
            return MarketplaceClient(_Cfg())


class TestMarketplaceClientInit:
    def test_init_reads_config(self, tmp_path):
        client = _make_simple_client(tmp_path)
        assert urlparse(client._base_url).hostname == "mp.example.com"

    def test_init_default_url(self, tmp_path):
        class _Cfg:
            raw = {"marketplace": {}}

        with patch.object(Path, "mkdir"):
            with patch.object(Path, "chmod"):
                client = MarketplaceClient(_Cfg())
        assert "xcore.dev" in client._base_url


class TestHashKey:
    def test_http_get_invalid_scheme(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with pytest.raises(MarketplaceError, match="protocol"):
            client._http_get("ftp://bad.url/plugins")

    def test_http_post_invalid_scheme(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with pytest.raises(MarketplaceError, match="protocol"):
            client._http_post("ftp://bad.url/plugins/x/rate", {"score": 5})

    def test_http_get_http_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        err = HTTPError("http://x.com", 404, "Not Found", {}, None)
        with patch("xcore.marketplace.client.urlopen", side_effect=err):
            with pytest.raises(MarketplaceError, match="HTTP 404"):
                client._http_get("https://mp.example.com/plugins")

    def test_http_get_url_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch("xcore.marketplace.client.urlopen", side_effect=URLError("connection refused")):
            with pytest.raises(MarketplaceError, match="Connection"):
                client._http_get("https://mp.example.com/plugins")

    def test_http_get_generic_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch("xcore.marketplace.client.urlopen", side_effect=RuntimeError("boom")):
            with pytest.raises(MarketplaceError, match="Network"):
                client._http_get("https://mp.example.com/plugins")

    def test_http_post_http_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        err = HTTPError("https://mp.example.com", 403, "Forbidden", {}, None)
        with patch("xcore.marketplace.client.urlopen", side_effect=err):
            with pytest.raises(MarketplaceError, match="HTTP 403"):
                client._http_post("https://mp.example.com/plugins/x/rate", {"score": 5})

    def test_http_post_url_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch("xcore.marketplace.client.urlopen", side_effect=URLError("timeout")):
            with pytest.raises(MarketplaceError, match="Connection"):
                client._http_post("https://mp.example.com/p/rate", {"score": 5})

    def test_http_get_success(self, tmp_path):
        client = _make_simple_client(tmp_path)
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps([{"name": "auth"}]).encode()
        with patch("xcore.marketplace.client.urlopen", return_value=mock_resp):
            result = client._http_get("https://mp.example.com/plugins")
        assert isinstance(result, list)

    def test_http_post_success(self, tmp_path):
        client = _make_simple_client(tmp_path)
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode()
        with patch("xcore.marketplace.client.urlopen", return_value=mock_resp):
            result = client._http_post("https://mp.example.com/plugins/x/rate", {"score": 5})
        assert result["status"] == "ok"


class TestHeaders:
    def test_headers_with_api_key(self, tmp_path):
        client = _make_simple_client(tmp_path, api_key="my-key")
        headers = client._headers()
        assert "Authorization" in headers
        assert "my-key" in headers["Authorization"]

    def test_headers_without_api_key(self, tmp_path):
        client = _make_simple_client(tmp_path, api_key="")
        headers = client._headers()
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/json"


class TestCache:
    def test_cache_path(self, tmp_path):
        client = _make_simple_client(tmp_path)
        path = client._cache_path("my_key")
        assert path.name == "my_key.json"

    def test_cache_path_sanitizes_key(self, tmp_path):
        client = _make_simple_client(tmp_path)
        path = client._cache_path("search/auth plugin")
        assert "/" not in path.name
        assert " " not in path.name

    def test_read_cache_missing_file(self, tmp_path):
        client = _make_simple_client(tmp_path)
        result = client._read_cache("nonexistent_key")
        assert result is None

    def test_write_and_read_cache(self, tmp_path):
        client = _make_simple_client(tmp_path)
        client._cache_dir = tmp_path

        def real_cache_path(key):
            safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
            return tmp_path / f"{safe_key}.json"

        client._cache_path = real_cache_path
        client._write_cache("list", [{"name": "auth"}])
        result = client._read_cache("list")
        assert result == [{"name": "auth"}]

    def test_read_cache_expired(self, tmp_path):
        client = _make_simple_client(tmp_path)
        client._cache_ttl = 1

        def real_cache_path(key):
            safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
            return tmp_path / f"{safe_key}.json"

        client._cache_path = real_cache_path
        path = real_cache_path("old_key")
        path.write_text(json.dumps({"_ts": time.time() - 100, "data": "old"}))
        result = client._read_cache("old_key")
        assert result is None

    def test_read_cache_corrupted(self, tmp_path):
        client = _make_simple_client(tmp_path)

        def real_cache_path(key):
            return tmp_path / f"{key}.json"

        client._cache_path = real_cache_path
        real_cache_path("bad").write_text("NOT JSON {{")
        result = client._read_cache("bad")
        assert result is None

    def test_invalidate_specific_key(self, tmp_path):
        client = _make_simple_client(tmp_path)

        def real_cache_path(key):
            return tmp_path / f"{key}.json"

        client._cache_path = real_cache_path
        f = real_cache_path("list")
        f.write_text(json.dumps({"_ts": time.time(), "data": []}))
        client.invalidate_cache("list")
        assert not f.exists()

    def test_invalidate_all(self, tmp_path):
        client = _make_simple_client(tmp_path)

        def real_cache_path(key):
            return tmp_path / f"{key}.json"

        client._cache_path = real_cache_path
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        import xcore.marketplace.client as mkt_module
        original_cache_dir = mkt_module.CACHE_DIR
        mkt_module.CACHE_DIR = tmp_path
        try:
            client.invalidate_cache()
        finally:
            mkt_module.CACHE_DIR = original_cache_dir
        assert list(tmp_path.glob("*.json")) == []


class TestPublicAPI:
    @pytest.mark.asyncio
    async def test_rate_plugin_invalid_score(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with pytest.raises(ValueError, match="Score"):
            await client.rate_plugin("auth", score=6)

    @pytest.mark.asyncio
    async def test_rate_plugin_valid_score(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_post", return_value={"status": "ok"}) as mock_post:
            result = await client.rate_plugin("auth", score=5)
            mock_post.assert_called_once()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_plugin_returns_none_on_error(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_get", side_effect=MarketplaceError("not found")):
            result = await client.get_plugin("unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_plugins(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_get", return_value=[{"name": "auth"}]) as mock_get:
            result = await client.list_plugins()
        assert result == [{"name": "auth"}]

    @pytest.mark.asyncio
    async def test_trending(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_get", return_value=[{"name": "popular"}]) as mock_get:
            result = await client.trending(limit=5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_get", return_value=[]) as mock_get:
            result = await client.search("auth")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_versions(self, tmp_path):
        client = _make_simple_client(tmp_path)
        with patch.object(client, "_get", return_value=[{"version": "1.0"}]) as mock_get:
            result = await client.get_versions("auth")
        assert result[0]["version"] == "1.0"

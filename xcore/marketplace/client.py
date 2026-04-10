"""
marketplace/client.py — Client HTTP générique pour le marketplace xcore.

Configuration dans xcore.yaml :
    marketplace:
      url: https://marketplace.xcore.dev   # URL de base de l'API
      api_key: ${XCORE_MARKETPLACE_KEY}    # clé API optionnelle
      timeout: 10                          # timeout en secondes
      cache_ttl: 300                       # cache local en secondes

Contrat API attendu (REST JSON) :
    GET  /plugins                     → liste paginée
    GET  /plugins/trending            → plugins populaires
    GET  /plugins/search?q=<query>    → recherche
    GET  /plugins/<name>              → détails
    POST /plugins/<name>/rate         → noter { score: 1-5 }
    GET  /plugins/<name>/versions     → versions disponibles
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger("xcore.marketplace.client")

DEFAULT_URL = "https://marketplace.xcore.dev"
DEFAULT_TIMEOUT = 10
CACHE_DIR = Path.home() / ".xcore" / "marketplace_cache"


class MarketplaceError(Exception):
    pass


class MarketplaceClient:
    """
    Client HTTP générique pour le marketplace xcore.

    Lit sa configuration depuis XcoreConfig.raw["marketplace"].
    Supporte un cache local JSON pour réduire les appels réseau.

    Usage:
        client = MarketplaceClient(config)

        plugins = await client.list_plugins()
        trending = await client.trending()
        results = await client.search("auth")
        plugin = await client.get_plugin("auth")
        await client.rate_plugin("auth", score=5)
    """

    def __init__(self, config) -> None:
        raw_mkt = config.raw.get("marketplace", {})
        self._base_url = raw_mkt.get("url", DEFAULT_URL).rstrip("/")
        self._api_key = raw_mkt.get("api_key", "")
        self._timeout = raw_mkt.get("timeout", DEFAULT_TIMEOUT)
        self._cache_ttl = raw_mkt.get("cache_ttl", 300)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── API publique ──────────────────────────────────────────

    async def list_plugins(self, page: int = 1, per_page: int = 20) -> list[dict]:
        """Liste tous les plugins du marketplace."""
        return await self._get(
            f"/plugins?page={page}&per_page={per_page}", cache_key="list"
        )

    async def trending(self, limit: int = 10) -> list[dict]:
        """Retourne les plugins populaires."""
        return await self._get(f"/plugins/trending?limit={limit}", cache_key="trending")

    async def search(self, query: str) -> list[dict]:
        """Recherche des plugins par nom, description ou auteur."""
        q = urlencode({"q": query})
        return await self._get(f"/plugins/search?{q}", cache_key=f"search_{query}")

    async def get_plugin(self, name: str) -> dict | None:
        """Retourne les détails d'un plugin ou None s'il n'existe pas."""
        try:
            return await self._get(f"/plugins/{name}", cache_key=f"plugin_{name}")
        except MarketplaceError:
            return None

    async def get_versions(self, name: str) -> list[dict]:
        """Retourne toutes les versions disponibles d'un plugin."""
        return await self._get(
            f"/plugins/{name}/versions", cache_key=f"versions_{name}"
        )

    async def rate_plugin(self, name: str, score: int) -> dict:
        """Note un plugin (score entre 1 et 5)."""
        if not 1 <= score <= 5:
            raise ValueError(f"Score invalide : {score}. Valeurs : 1-5")
        return await self._post(f"/plugins/{name}/rate", {"score": score})

    # ── HTTP ──────────────────────────────────────────────────

    async def _get(self, path: str, cache_key: str | None = None) -> Any:
        import asyncio

        # Cache local
        if cache_key:
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached

        url = self._base_url + path
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: self._http_get(url))

        if cache_key:
            self._write_cache(cache_key, data)

        return data

    async def _post(self, path: str, body: dict) -> Any:
        import asyncio

        url = self._base_url + path
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._http_post(url, body))

    def _http_get(self, url: str) -> Any:
        scheme = urlparse(url).scheme
        if scheme not in ("http", "https"):
            raise MarketplaceError(
                f"Sécurité : protocole '{scheme}' non autorisé pour {url}"
            )
        req = Request(url, headers=self._headers())
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            raise MarketplaceError(f"HTTP {e.code} : {url}") from e
        except URLError as e:
            raise MarketplaceError(f"Connexion impossible : {e.reason}") from e
        except Exception as e:
            raise MarketplaceError(f"Erreur réseau : {e}") from e

    def _http_post(self, url: str, body: dict) -> Any:
        scheme = urlparse(url).scheme
        if scheme not in ("http", "https"):
            raise MarketplaceError(
                f"Sécurité : protocole '{scheme}' non autorisé pour {url}"
            )
        data = json.dumps(body).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={
                **self._headers(),
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            raise MarketplaceError(f"HTTP {e.code} : {url}") from e
        except URLError as e:
            raise MarketplaceError(f"Connexion impossible : {e.reason}") from e

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "User-Agent": "xcore-cli/2.0"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    # ── Cache local ───────────────────────────────────────────

    def _cache_path(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return CACHE_DIR / f"{safe_key}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            if time.time() - raw.get("_ts", 0) > self._cache_ttl:
                return None
            return raw.get("data")
        except Exception:
            return None

    def _write_cache(self, key: str, data: Any) -> None:
        path = self._cache_path(key)
        try:
            path.write_text(json.dumps({"_ts": time.time(), "data": data}))
        except Exception:
            pass

    def invalidate_cache(self, key: str | None = None) -> None:
        """Vide le cache local (tout ou clé spécifique)."""
        if key:
            self._cache_path(key).unlink(missing_ok=True)
        else:
            for f in CACHE_DIR.glob("*.json"):
                f.unlink(missing_ok=True)

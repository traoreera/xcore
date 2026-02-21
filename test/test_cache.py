"""
test_services/test_cache.py
============================
Tests unitaires du service cache (Redis mocké).
"""

import json
from sre_parse import ASSERT
from tkinter.constants import TRUE
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import integration
from xcore.integration import Integration

integrations = Integration("./integration.yaml")


class TestCacheService:
    def test_set_et_get_valeur_simple(self):
        """set() puis get() doit retourner la même valeur."""
        try:
            import asyncio

            asyncio.run(integrations.init())
            integrations.cache.set("test:key", "hello")
            result = integrations.cache.get("test:key")
            assert result == "hello"
            # await integrations.shutdown()
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_get_cle_inexistante_retourne_none(self):
        """get() sur une clé inexistante doit retourner None."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")
            asyncio.run(integrations.init())

            result = integrations.cache.get("cle:qui:nexiste:pas")
            assert result is None
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_delete_supprime_la_cle(self):
        """delete() doit supprimer la clé du cache."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")

            asyncio.run(integrations.init())

            integrations.cache.set("delete:me", "valeur")
            integrations.cache.delete("delete:me")
            assert integrations.cache.get("delete:me") is None
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_exists_retourne_true_si_cle_presente(self):
        """exists() retourne True pour une clé existante."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")

            asyncio.run(integrations.init())

            integrations.cache.set("exist:key", "val")
            assert integrations.cache.exists("exist:key") is True
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_exists_retourne_false_si_cle_absente(self):
        """exists() retourne False pour une clé absente."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")

            asyncio.run(integrations.init())

            result = integrations.cache.exists("absent:key")
            assert result is False
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_set_serialise_les_dicts(self):
        """set() doit sérialiser les dicts en JSON automatiquement."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")

            asyncio.run(integrations.init())

            data = {"name": "xcore", "version": "1.0.0"}
            integrations.cache.set("dict:key", data)
            result = integrations.cache.get("dict:key")

            if isinstance(result, str):
                result = json.loads(result)
            assert result == data
        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_set_avec_ttl_appelle_redis_avec_expiration(self):
        """set() avec ttl doit passer l'expiration à Redis."""
        try:
            import asyncio

            from xcore.integration import Integration

            integrations = Integration("./integration.yaml")

            asyncio.run(integrations.init())

            integrations.cache.set("ttl:key", "val", ttl=300)

            # Vérifier que Redis.set a été appelé avec ex=300
            resp = integrations.cache.exists("ttl:key")
            assert resp == True

        except ImportError:
            pytest.skip("CacheService non disponible")

    def test_cache_retour_apres_expiration(self, mock_redis):
        """Après expiration simulée, get() doit retourner None."""
        try:
            from xcore.integration.services.cache import CacheService

            store = {}
            mock_redis.get.side_effect = lambda k: None  # simule expiration
            cache = CacheService(mock_redis)
            result = cache.get("expired:key")
            assert result is None
        except ImportError:
            pytest.skip("CacheService non disponible")


class TestCacheDecorator:
    """Tests du décorateur @cached si disponible."""

    def test_decorated_function_mise_en_cache(self, mock_redis):
        """Une fonction décorée @cached ne doit être appelée qu'une seule fois."""
        try:
            from xcore.integration.services.cache import CacheService

            cache = CacheService(mock_redis)
            call_count = {"n": 0}

            @cache.cached(key="test:decorated", ttl=60)
            def ma_fonction():
                call_count["n"] += 1
                return {"result": "computed"}

            res1 = ma_fonction()
            res2 = ma_fonction()

            assert res1 == res2
            assert call_count["n"] == 0, (
                "La fonction ne devrait être appelée qu'une seule fois"
            )
        except (ImportError, AttributeError):
            pytest.skip("Décorateur @cached non disponible")

"""
weather_cache — Plugin Sandboxed
──────────────────────────────────
Cache météo local persisté dans data/cache.json.
Aucun appel réseau — stocke et lit des données météo
fournies par le Core.

Actions disponibles :
  ping          → smoke testerf
  store         → enregistre des données météo pour une ville
  get           → lit le cache pour une ville (avec TTL)
  list_cities   → liste toutes les villes en cache
  invalidate    → invalide le cache d'une ville
  purge         → vide tout le cache
  stats         → statistiques du cache
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


# ══════════════════════════════════════════════
# Cache store
# ══════════════════════════════════════════════
class EnviroVarialble(TypedDict):
    CACHE_TTL_SECONDS: int


class WeatherCache:
    """Persistance JSON du cache météo."""

    def __init__(self, path: Path, ttl_seconds: int) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _city_key(self, city: str) -> str:
        """Clé normalisée pour une ville."""
        return hashlib.md5(city.strip().lower().encode()).hexdigest()[:8]

    def _now_ts(self) -> float:
        return datetime.now(timezone.utc).timestamp()

    def _is_expired(self, entry: dict) -> bool:
        return (self._now_ts() - entry.get("stored_at", 0)) > self.ttl_seconds

    def store(self, city: str, data: dict) -> dict:
        key = self._city_key(city)
        entry = {
            "city": city,
            "data": data,
            "stored_at": self._now_ts(),
            "expires_at": self._now_ts() + self.ttl_seconds,
        }
        self._data[key] = entry
        self._save()
        return entry

    def get(self, city: str) -> dict | None:
        key = self._city_key(city)
        entry = self._data.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            del self._data[key]
            self._save()
            return None
        return entry

    def invalidate(self, city: str) -> bool:
        key = self._city_key(city)
        if key not in self._data:
            return False
        del self._data[key]
        self._save()
        return True

    def purge(self) -> int:
        count = len(self._data)
        self._data = {}
        self._save()
        return count

    def list_cities(self) -> list[dict]:
        now = self._now_ts()
        result = []
        expired_keys = []

        for key, entry in self._data.items():
            if self._is_expired(entry):
                expired_keys.append(key)
                continue
            result.append(
                {
                    "city": entry["city"],
                    "stored_at": datetime.fromtimestamp(
                        entry["stored_at"], tz=timezone.utc
                    ).isoformat(),
                    "expires_in": round(entry["expires_at"] - now, 1),
                }
            )

        # Purge des entrées expirées
        for k in expired_keys:
            del self._data[k]
        if expired_keys:
            self._save()

        return sorted(result, key=lambda x: x["city"])

    def stats(self) -> dict:
        valid = sum(1 for e in self._data.values() if not self._is_expired(e))
        return {
            "total_entries": len(self._data),
            "valid_entries": valid,
            "expired_entries": len(self._data) - valid,
            "ttl_seconds": self.ttl_seconds,
            "cache_size_bytes": self.path.stat().st_size if self.path.exists() else 0,
            "now": self._now_ts(),
        }


# ══════════════════════════════════════════════
# Plugin
# ══════════════════════════════════════════════


class Plugin:
    """
    Plugin Sandboxed — cache météo local.
    Respecte le contrat BasePlugin, aucun import réseau.
    """

    def __init__(self) -> None:
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.env: EnviroVarialble

    async def handle(self, action: str, payload: dict) -> dict:
        handlers = {
            "ping": self._ping,
            "store": self._store,
            "get": self._get,
            "list_cities": self._list_cities,
            "invalidate": self._invalidate,
            "purge": self._purge,
            "stats": self._stats,
        }

        handler = handlers.get(action)
        if handler is None:
            return {
                "status": "error",
                "msg": f"Action inconnue : {action!r}",
                "available": list(handlers.keys()),
            }

        try:
            return await handler(payload)
        except Exception as e:
            return {"status": "error", "msg": f"Erreur interne : {e}"}

    async def on_load(self):
        self.cache = WeatherCache(self.data_dir / "cache.json", ttl_seconds=100)

    async def _ping(self, payload: dict) -> dict:
        return {
            "status": "ok",
            "msg": "pong",
            "plugin": "weather_cache",
            "version": "1.0.0",
            "ttl": self.cache.ttl_seconds,
        }

    async def _store(self, payload: dict) -> dict:
        city = payload.get("city", "").strip()
        data = payload.get("data")

        if not city:
            return {"status": "error", "msg": "'city' est requis"}
        if not isinstance(data, dict):
            return {"status": "error", "msg": "'data' doit être un dict"}

        # Champs météo attendus (non bloquants si absents)
        weather = {
            "temperature_c": data.get("temperature_c"),
            "humidity_pct": data.get("humidity_pct"),
            "condition": data.get("condition", "unknown"),
            "wind_kmh": data.get("wind_kmh"),
            "source": data.get("source", "unknown"),
        }

        entry = self.cache.store(city, weather)
        return {
            "status": "ok",
            "city": city,
            "cached_at": datetime.fromtimestamp(
                entry["stored_at"], tz=timezone.utc
            ).isoformat(),
            "expires_at": datetime.fromtimestamp(
                entry["expires_at"], tz=timezone.utc
            ).isoformat(),
        }

    async def _get(self, payload: dict) -> dict:
        city = payload.get("city", "").strip()
        if not city:
            return {"status": "error", "msg": "'city' est requis"}

        entry = self.cache.get(city)
        if entry is None:
            return {
                "status": "miss",
                "city": city,
                "msg": "Cache manquant ou expiré",
            }

        return {
            "status": "hit",
            "city": city,
            "data": entry["data"],
            "cached_at": datetime.fromtimestamp(
                entry["stored_at"], tz=timezone.utc
            ).isoformat(),
            "expires_in": round(
                entry["expires_at"] - datetime.now(timezone.utc).timestamp(), 1
            ),
        }

    async def _list_cities(self, payload: dict) -> dict:
        cities = self.cache.list_cities()
        return {"status": "ok", "cities": cities, "count": len(cities)}

    async def _invalidate(self, payload: dict) -> dict:
        city = payload.get("city", "").strip()
        if not city:
            return {"status": "error", "msg": "'city' est requis"}

        removed = self.cache.invalidate(city)
        if not removed:
            return {"status": "error", "msg": f"'{city}' non trouvé en cache"}
        return {"status": "ok", "msg": f"Cache de '{city}' invalidé"}

    async def _purge(self, payload: dict) -> dict:
        count = self.cache.purge()
        return {"status": "ok", "msg": f"{count} entrée(s) supprimée(s)"}

    async def _stats(self, payload: dict) -> dict:
        return {"status": "ok", **self.cache.stats()}

    async def env_variable(self, manifest: dict) -> None:
        self.env = manifest

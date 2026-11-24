"""
store.py — Où vivent les VERSIONS de clé de chaque organisation (#312).

Ce qui est rangé n'est pas secret : pour chaque organisation, la liste de ses versions
et, pour chacune, le numéro de la clé maîtresse dont elle dérive. Mais c'est durable et
partagé : une rotation faite par un worker doit être vue des autres, et survivre à un
redémarrage — sinon les secrets scellés sous la version 2 ne sont plus relisibles.

    memory    tests et développement — perdu à l'arrêt, propre au processus
    file      un fichier JSON — durable, un seul hôte
    database  une table de `services.databases` — durable et partagé entre workers
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

TABLE = "xcore_key_versions"


@dataclass(frozen=True)
class KeyVersion:
    """Une version de clé d'une organisation, et la clé maîtresse dont elle dérive."""

    tenant_id: str
    version: int
    master_id: int
    created_at: float = field(default_factory=time.time, compare=False)


class VersionConflict(Exception):
    """Cette version existe déjà pour cette organisation (rotation concurrente)."""


class VersionStore(Protocol):
    durable: bool  # survit à un redémarrage
    shared: bool  # vu des autres processus (donc à relire périodiquement)

    async def setup(self) -> None: ...

    async def load(self) -> dict[str, list[KeyVersion]]:
        """Toutes les versions, par organisation, triées par numéro."""

    async def append(self, record: KeyVersion) -> None:
        """Inscrit une version. Lève VersionConflict si elle existe déjà."""


def _sorted(versions: dict[str, list[KeyVersion]]) -> dict[str, list[KeyVersion]]:
    return {t: sorted(v, key=lambda r: r.version) for t, v in versions.items() if v}


class MemoryVersionStore:
    durable = False
    shared = False

    def __init__(self) -> None:
        self._versions: dict[str, list[KeyVersion]] = {}

    async def setup(self) -> None:
        return None

    async def load(self) -> dict[str, list[KeyVersion]]:
        return _sorted({t: list(v) for t, v in self._versions.items()})

    async def append(self, record: KeyVersion) -> None:
        existing = self._versions.setdefault(record.tenant_id, [])
        if any(v.version == record.version for v in existing):
            raise VersionConflict(f"{record.tenant_id} v{record.version}")
        existing.append(record)


class FileVersionStore:
    """Un fichier JSON, réécrit atomiquement, sous verrou de fichier (un hôte)."""

    durable = True
    shared = True

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def setup(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, list[KeyVersion]]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        return {
            tenant: [
                KeyVersion(
                    tenant, int(r["version"]), int(r["master_id"]), r["created_at"]
                )
                for r in records
            ]
            for tenant, records in (raw.get("tenants") or {}).items()
        }

    @contextlib.contextmanager
    def _locked(self):
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        with open(lock_path, "a+") as lock:
            try:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX)
            except (
                ImportError
            ):  # pragma: no cover - Windows : pas de verrou consultatif
                pass
            yield

    def _append(self, record: KeyVersion) -> None:
        with self._locked():
            versions = self._read()
            existing = versions.setdefault(record.tenant_id, [])
            if any(v.version == record.version for v in existing):
                raise VersionConflict(f"{record.tenant_id} v{record.version}")
            existing.append(record)
            payload = {
                "tenants": {
                    tenant: [
                        {
                            "version": v.version,
                            "master_id": v.master_id,
                            "created_at": v.created_at,
                        }
                        for v in records
                    ]
                    for tenant, records in _sorted(versions).items()
                }
            }
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)  # jamais de fichier à moitié écrit

    async def load(self) -> dict[str, list[KeyVersion]]:
        return _sorted(await asyncio.to_thread(self._read))

    async def append(self, record: KeyVersion) -> None:
        await asyncio.to_thread(self._append, record)


class DatabaseVersionStore:
    """Une table `xcore_key_versions` dans une connexion de `services.databases`."""

    durable = True
    shared = True

    def __init__(self, adapter: Any, table: str = TABLE) -> None:
        from ..database.sqlexec import dialect_of, engine_of

        engine = engine_of(adapter)
        if engine is None or dialect_of(engine) is None:
            raise ValueError("la connexion choisie n'est pas une base SQL initialisée")
        if not table.replace("_", "").isalnum():
            raise ValueError(f"nom de table invalide : {table!r}")
        self._engine = engine
        self._table = table

    async def _run(self, statement: str, params: dict | None = None) -> Any:
        from ..database.sqlexec import run_statement

        return await run_statement(self._engine, statement, params)

    async def setup(self) -> None:
        create = (
            f"CREATE TABLE IF NOT EXISTS {self._table} ("
            "tenant_id VARCHAR(255) NOT NULL, "
            "version INTEGER NOT NULL, "
            "master_id INTEGER NOT NULL, "
            "created_at DOUBLE PRECISION NOT NULL, "
            "PRIMARY KEY (tenant_id, version))"
        )
        try:
            await self._run(create)
        except Exception:
            # Deux processus qui démarrent ensemble : si la table est là, tout va bien.
            await self._run(f"SELECT 1 FROM {self._table} WHERE 1 = 0")

    async def load(self) -> dict[str, list[KeyVersion]]:
        rows = (
            await self._run(
                f"SELECT tenant_id, version, master_id, created_at FROM {self._table}"
            )
        ).all()
        versions: dict[str, list[KeyVersion]] = {}
        for tenant, version, master_id, created_at in rows:
            versions.setdefault(tenant, []).append(
                KeyVersion(tenant, int(version), int(master_id), float(created_at))
            )
        return _sorted(versions)

    async def append(self, record: KeyVersion) -> None:
        from sqlalchemy.exc import IntegrityError

        try:
            await self._run(
                f"INSERT INTO {self._table} (tenant_id, version, master_id, created_at) "
                "VALUES (:tenant_id, :version, :master_id, :created_at)",
                {
                    "tenant_id": record.tenant_id,
                    "version": record.version,
                    "master_id": record.master_id,
                    "created_at": record.created_at,
                },
            )
        except IntegrityError as e:  # clé primaire : un autre worker a pris ce numéro
            raise VersionConflict(f"{record.tenant_id} v{record.version}") from e

"""
sqlexec.py — Exécuter UNE instruction SQL dans sa propre transaction, sur le moteur
d'un adaptateur de `services.databases`, qu'il soit asynchrone ou synchrone.

Sert aux services du noyau qui tiennent un peu d'état en base (baux du scheduler,
versions de clés, file outbox) sans passer par les sessions des plugins.
"""

from __future__ import annotations

import asyncio
from typing import Any

# Horloge de la BASE, en secondes epoch (flottant), par dialecte. Les services qui
# comparent des échéances le font dans l'instruction SQL, jamais avec l'horloge du
# process : deux machines désynchronisées ne se marchent pas dessus.
#   - postgresql : clock_timestamp() et non now(), figé au début de la transaction.
#   - sqlite     : julianday('now') — précision milliseconde, toutes versions.
NOW_EPOCH = {
    "postgresql": "EXTRACT(EPOCH FROM clock_timestamp())",
    "mysql": "UNIX_TIMESTAMP(NOW(6))",
    "mariadb": "UNIX_TIMESTAMP(NOW(6))",
    "sqlite": "((julianday('now') - 2440587.5) * 86400.0)",
}
FLOAT_TYPE = {
    "postgresql": "DOUBLE PRECISION",
    "mysql": "DOUBLE",
    "mariadb": "DOUBLE",
    "sqlite": "REAL",
}
# Dialectes qui savent `INSERT … ON CONFLICT` (les autres : `INSERT IGNORE`).
ON_CONFLICT = frozenset({"postgresql", "sqlite"})


def engine_of(adapter: Any) -> Any | None:
    """Moteur SQLAlchemy d'un adaptateur (`AsyncSQLAdapter` / `SQLAdapter`), ou None."""
    return getattr(adapter, "_engine", None) or getattr(adapter, "engine", None)


def dialect_of(engine: Any) -> str | None:
    return getattr(getattr(engine, "dialect", None), "name", None)


async def run_statement(engine: Any, statement: str, params: dict | None = None) -> Any:
    """Exécute `statement` dans une transaction courte et rend le résultat (déjà lu)."""
    from sqlalchemy import text

    clause = text(statement)
    if hasattr(engine, "sync_engine"):  # AsyncEngine
        async with engine.begin() as conn:
            return _buffered(await conn.execute(clause, params or {}))

    def _sync() -> Any:
        with engine.begin() as conn:
            return _buffered(conn.execute(clause, params or {}))

    # Moteur synchrone : hors du loop, sinon chaque requête gèlerait l'application.
    return await asyncio.to_thread(_sync)


class _Result:
    """Résultat détaché de sa connexion : `rowcount` et les lignes, lues avant le commit."""

    __slots__ = ("rowcount", "rows")

    def __init__(self, rowcount: int, rows: list) -> None:
        self.rowcount = rowcount
        self.rows = rows

    def first(self) -> Any | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list:
        return self.rows


def _buffered(result: Any) -> _Result:
    rows = list(result.fetchall()) if result.returns_rows else []
    return _Result(result.rowcount, rows)

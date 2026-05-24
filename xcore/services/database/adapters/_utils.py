"""
_utils.py — Normalisation des connect_args selon le driver SQL.

Chaque driver DBAPI a ses propres paramètres de connexion acceptés.
Passer un argument inconnu lève une TypeError au connect().
"""

from __future__ import annotations

import logging

logger = logging.getLogger("xcore.services.database")

# Paramètres valides par driver (ceux qu'on expose dans xcore.yaml)
_VALID_CONNECT_ARGS: dict[str, set[str]] = {
    # aiomysql / pymysql / mysqlclient
    "aiomysql": {
        "connect_timeout",
        "charset",
        "autocommit",
        "sql_mode",
        "init_command",
        "ssl",
    },
    "pymysql": {
        "connect_timeout",
        "read_timeout",
        "write_timeout",
        "charset",
        "autocommit",
        "sql_mode",
        "init_command",
        "ssl",
        "ssl_ca",
        "ssl_cert",
        "ssl_key",
    },
    # asyncpg / psycopg2 / psycopg3
    "asyncpg": {
        "timeout",
        "command_timeout",
        "statement_cache_size",
        "ssl",
    },
    "psycopg2": {
        "connect_timeout",
        "options",
        "sslmode",
        "sslcert",
        "sslkey",
        "sslrootcert",
        "application_name",
    },
    "psycopg": {  # psycopg3
        "connect_timeout",
        "options",
        "sslmode",
        "application_name",
    },
    # aiosqlite / sqlite
    "aiosqlite": {"timeout", "check_same_thread", "uri"},
    "pysqlite": {"timeout", "check_same_thread", "uri"},
}


def _detect_driver(url: str) -> str:
    """Détecte le driver depuis l'URL SQLAlchemy."""
    url_lower = url.lower()
    for driver in _VALID_CONNECT_ARGS:
        if driver in url_lower:
            return driver
    # Fallback : on ne filtre pas
    return ""


def sanitize_connect_args(url: str, connect_args: dict) -> dict:
    """
    Filtre connect_args pour ne garder que les clés valides pour le driver.
    Log un warning pour chaque clé ignorée.
    """
    if not connect_args:
        return {}

    driver = _detect_driver(url)
    valid = _VALID_CONNECT_ARGS.get(driver)

    if valid is None:
        # Driver inconnu → on passe tout et on laisse le driver lever l'erreur
        return connect_args

    filtered = {}
    for key, value in connect_args.items():
        if key in valid:
            filtered[key] = value
        else:
            logger.warning(
                f"connect_args : '{key}' ignoré pour le driver '{driver}' "
                f"(non supporté). Clés valides : {sorted(valid)}"
            )

    return filtered

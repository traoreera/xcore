"""
_utils.py — Normalisation des connect_args et isolation_level selon le driver SQL.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("xcore.services.database")


# Drivers pour lesquels pool_pre_ping est incompatible
# → on désactive et on compense avec pool_recycle + event listener
_PRE_PING_BROKEN = {"aiomysql", "cymysql"}


def is_pre_ping_safe(url: str) -> bool:
    """
    pool_pre_ping=True est incompatible avec aiomysql (ping() signature différente).
    Pour ces drivers on retourne False → compensation via pool_recycle + event.
    """
    return detect_driver(url) not in _PRE_PING_BROKEN


_VALID_CONNECT_ARGS: dict[str, set[str]] = {
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
    "psycopg": {
        "connect_timeout",
        "options",
        "sslmode",
        "application_name",
    },
    "aiosqlite": {"timeout", "check_same_thread", "uri"},
    "pysqlite": {"timeout", "check_same_thread", "uri"},
}

# Isolation levels valides par famille de BDD
_VALID_ISOLATION_LEVELS: dict[str, set[str]] = {
    "sqlite": {"READ UNCOMMITTED", "SERIALIZABLE", "AUTOCOMMIT"},
    "mysql": {
        "READ UNCOMMITTED",
        "READ COMMITTED",
        "REPEATABLE READ",
        "SERIALIZABLE",
        "AUTOCOMMIT",
    },
    "postgresql": {
        "READ UNCOMMITTED",
        "READ COMMITTED",
        "REPEATABLE READ",
        "SERIALIZABLE",
        "AUTOCOMMIT",
    },
}


def detect_driver(url: str) -> str:
    """
    Détecte le driver depuis l'URL SQLAlchemy.
    Ex: 'mysql+aiomysql://...' → 'aiomysql'
        'sqlite+aiosqlite://...' → 'aiosqlite'
        'postgresql+asyncpg://...' → 'asyncpg'
    """
    url_lower = url.lower()

    # Ordre important : tester les drivers spécifiques avant les génériques
    driver_tokens = [
        "aiomysql",
        "pymysql",
        "asyncpg",
        "aiosqlite",
        "psycopg2",
        "psycopg",
        "pysqlite",
        "mysqlconnector",
        "cymysql",
    ]
    for driver in driver_tokens:
        if driver in url_lower:
            return driver

    return ""


def detect_db_family(url: str) -> str:
    """
    Détecte la famille de BDD pour la validation de l'isolation_level.
    Ex: 'mysql+aiomysql://...' → 'mysql'
    """
    url_lower = url.lower()
    if url_lower.startswith("sqlite"):
        return "sqlite"
    if url_lower.startswith("mysql") or url_lower.startswith("mariadb"):
        return "mysql"
    if url_lower.startswith("postgresql") or url_lower.startswith("postgres"):
        return "postgresql"
    return ""


def sanitize_connect_args(url: str, connect_args: dict) -> dict:
    """
    Filtre connect_args pour ne garder que les clés valides pour le driver détecté.
    Log un warning pour chaque clé ignorée, sans planter.
    """
    if not connect_args:
        return {}

    driver = detect_driver(url)
    valid = _VALID_CONNECT_ARGS.get(driver)

    if not valid:
        # Driver inconnu → on passe tout tel quel
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


def sanitize_isolation_level(url: str, isolation_level: str | None) -> str | None:
    """
    Valide l'isolation_level selon la famille de BDD.
    Retourne None (ignoré silencieusement) si incompatible.
    """
    if not isolation_level:
        return None

    family = detect_db_family(url)
    valid = _VALID_ISOLATION_LEVELS.get(family)

    if not valid:
        return isolation_level  # famille inconnue → on laisse passer

    level_upper = isolation_level.upper()
    if level_upper not in valid:
        logger.warning(
            f"isolation_level '{isolation_level}' ignoré pour '{family}' "
            f"(non supporté). Niveaux valides : {sorted(valid)}"
        )
        return None

    return level_upper

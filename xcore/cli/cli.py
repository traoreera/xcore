"""
main.py — Point d'entrée du CLI xcore.

Commandes :
    xcore plugin  list|install|remove|info|load|reload|sign|verify|validate|health
    xcore sandbox run|limits|network|fs <plugin>
    xcore marketplace list|trending|search|show|rate
    xcore services status
    xcore health
    xcore worker  start|stop|status|logs|inspect|purge|beat
"""

from __future__ import annotations

import asyncio
import sys

# ── Helpers partagés ──────────────────────────────────────────────────────────


def _add_config(p):
    p.add_argument(
        "--config", default=None, metavar="PATH", help="Chemin vers integration.yaml"
    )


def _add_loglevel(p):
    p.add_argument(
        "--loglevel",
        "-l",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Niveau de log (défaut: info)",
    )


def _add_detach(p):
    p.add_argument(
        "--detach",
        "-d",
        action="store_true",
        help="Lance en arrière-plan (PID dans .xcore/pids/)",
    )


def _add_api_args(p):
    p.add_argument(
        "--app",
        default="main:app",
        metavar="MODULE:ATTR",
        help="App FastAPI (défaut: main:app)",
    )
    p.add_argument(
        "--host", default="0.0.0.0", help="Adresse d'écoute uvicorn (défaut: 0.0.0.0)"
    )
    p.add_argument(
        "--port", "-p", type=int, default=8000, help="Port uvicorn (défaut: 8000)"
    )
    p.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help="Nombre de workers uvicorn (défaut: 1)",
    )
    p.add_argument(
        "--reload", action="store_true", help="Auto-reload (mode développement)"
    )


def _add_celery_args(p):
    p.add_argument(
        "--queues",
        "-Q",
        default=None,
        metavar="Q1,Q2",
        help="Files Celery (défaut: depuis integration.yaml)",
    )
    p.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=None,
        help="Concurrence Celery (défaut: depuis integration.yaml)",
    )
    p.add_argument(
        "--hostname", "-n", default=None, help="Nom du worker ex: worker1@%%h"
    )


def main() -> None:
    import argparse

    fmt = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        prog="xcore",
        description="xcore — framework plugin-first sur FastAPI",
        formatter_class=fmt,
    )
    parser.add_argument("--version", action="store_true", help="Affiche la version")
    subs = parser.add_subparsers(dest="command", title="commandes")

    # ── plugin ────────────────────────────────────────────────────────────────
    plugin_p = subs.add_parser(
        "plugin",
        help="Gestion des plugins",
        description="Installe, signe et inspecte les plugins.",
    )
    plugin_sub = plugin_p.add_subparsers(dest="subcommand")

    plugin_sub.add_parser("list", help="Liste les plugins installés")
    plugin_sub.add_parser("health", help="Health-check de tous les plugins")

    for _name, _help in [
        ("load", "Charge un plugin (API IPC)"),
        ("reload", "Recharge un plugin (API IPC)"),
    ]:
        _p = plugin_sub.add_parser(_name, help=_help)
        _p.add_argument("name")
        _p.add_argument("--host", default=None)
        _p.add_argument("--port", type=int, default=None)
        _p.add_argument("--path", default=None)
        _p.add_argument("--key", default=None)
        _add_config(_p)

    install_p = plugin_sub.add_parser("install", help="Installe un plugin")
    install_p.add_argument("name")
    install_p.add_argument(
        "--source", choices=["zip", "git", "marketplace"], default="marketplace"
    )
    install_p.add_argument("--url", default=None)
    _add_config(install_p)

    remove_p = plugin_sub.add_parser("remove", help="Supprime un plugin")
    remove_p.add_argument("name")
    _add_config(remove_p)

    info_p = plugin_sub.add_parser("info", help="Détails d'un plugin")
    info_p.add_argument("name")
    _add_config(info_p)

    sign_p = plugin_sub.add_parser("sign", help="Signe un plugin Trusted")
    sign_p.add_argument("path")
    sign_p.add_argument("--key", default=None)

    verify_p = plugin_sub.add_parser("verify", help="Vérifie la signature")
    verify_p.add_argument("path")
    verify_p.add_argument("--key", default=None)

    validate_p = plugin_sub.add_parser("validate", help="Valide le manifeste")
    validate_p.add_argument("path")
    validate_p.add_argument(
        "--check-breaking",
        metavar="SCHEMA_FILE",
        default=None,
        help="Chemin vers un schemas.json précédent pour détecter les breaking changes",
    )
    _add_config(validate_p)

    for _p in (plugin_p, install_p, remove_p, info_p):
        _add_config(_p) if not any(a.dest == "config" for a in _p._actions) else None

    # ── sandbox ───────────────────────────────────────────────────────────────
    sb_p = subs.add_parser("sandbox", help="Gestion du sandbox runtime")
    sb_sub = sb_p.add_subparsers(dest="subcommand")

    for _name, _help in [
        ("run", "Lance un plugin en sandbox isolé"),
        ("limits", "Limites ressources déclarées"),
        ("network", "Politique réseau"),
        ("fs", "Politique filesystem"),
    ]:
        _p = sb_sub.add_parser(_name, help=_help)
        _p.add_argument("name")
        _add_config(_p)

    # ── marketplace ───────────────────────────────────────────────────────────
    mkt_p = subs.add_parser("marketplace", help="Catalogue de plugins")
    mkt_sub = mkt_p.add_subparsers(dest="subcommand")

    mkt_sub.add_parser("list", help="Liste tous les plugins")
    mkt_sub.add_parser("trending", help="Plugins populaires")

    mkt_search = mkt_sub.add_parser("search", help="Recherche")
    mkt_search.add_argument("query")

    mkt_show = mkt_sub.add_parser("show", help="Détails d'un plugin")
    mkt_show.add_argument("name")

    mkt_rate = mkt_sub.add_parser("rate", help="Note un plugin")
    mkt_rate.add_argument("name")
    mkt_rate.add_argument("--score", type=int, choices=range(1, 6), required=True)

    for _p in (mkt_p, mkt_search, mkt_show, mkt_rate):
        _add_config(_p) if not any(a.dest == "config" for a in _p._actions) else None

    # ── services ──────────────────────────────────────────────────────────────
    svc_p = subs.add_parser("services", help="État des services xcore")
    svc_sub = svc_p.add_subparsers(dest="subcommand")
    svc_status = svc_sub.add_parser(
        "status", help="Affiche l'état de tous les services"
    )
    svc_status.add_argument("--json", action="store_true", help="Sortie JSON")
    _add_config(svc_status)

    # ── health ────────────────────────────────────────────────────────────────
    health_p = subs.add_parser("health", help="Health-check global")
    health_p.add_argument("--json", action="store_true")
    _add_config(health_p)

    # ── worker ────────────────────────────────────────────────────────────────
    worker_p = subs.add_parser(
        "worker",
        help="Gestion des processus FastAPI et Celery",
        description=(
            "Lance, arrête et surveille FastAPI (uvicorn) et Celery worker\n"
            "dans des processus séparés.\n\n"
            "Exemples :\n"
            "  xcore worker start              # API + Celery (foreground)\n"
            "  xcore worker start --detach     # arrière-plan, PIDs dans .xcore/pids/\n"
            "  xcore worker start api --reload # API seule en dev\n"
            "  xcore worker start celery -Q default,emails -c 4\n"
            "  xcore worker stop\n"
            "  xcore worker status\n"
            "  xcore worker logs celery --follow\n"
            "  xcore worker inspect\n"
            "  xcore worker beat --detach"
        ),
        formatter_class=fmt,
    )
    worker_sub = worker_p.add_subparsers(dest="worker_subcommand")

    # worker start
    start_p = worker_sub.add_parser(
        "start", help="Lance API et/ou Celery", formatter_class=fmt
    )
    start_p.add_argument(
        "target",
        nargs="?",
        choices=["api", "celery", "all"],
        default="all",
        help="Cible : api | celery | all (défaut: all)",
    )
    _add_config(start_p)
    _add_loglevel(start_p)
    _add_detach(start_p)
    _add_api_args(start_p)
    _add_celery_args(start_p)

    # worker stop
    stop_p = worker_sub.add_parser("stop", help="Arrête API et/ou Celery")
    stop_p.add_argument(
        "target", nargs="?", choices=["api", "celery", "all"], default="all"
    )
    _add_config(stop_p)

    # worker status
    wstatus_p = worker_sub.add_parser("status", help="État des processus")
    wstatus_p.add_argument("--json", action="store_true")
    _add_config(wstatus_p)

    # worker logs
    logs_p = worker_sub.add_parser(
        "logs",
        help="Affiche les logs",
        formatter_class=fmt,
        description=(
            "Exemples :\n"
            "  xcore worker logs\n"
            "  xcore worker logs api -n 100\n"
            "  xcore worker logs celery --follow"
        ),
    )
    logs_p.add_argument(
        "target", nargs="?", choices=["api", "celery", "all"], default="all"
    )
    logs_p.add_argument(
        "--lines", "-n", type=int, default=50, help="Nombre de lignes (défaut: 50)"
    )
    logs_p.add_argument(
        "--follow", "-f", action="store_true", help="Suit en temps réel (cible unique)"
    )
    _add_config(logs_p)

    # worker inspect
    inspect_p = worker_sub.add_parser(
        "inspect", help="Tâches enregistrées et workers actifs"
    )
    _add_config(inspect_p)

    # worker purge
    purge_p = worker_sub.add_parser(
        "purge",
        help="Vide une file d'attente Celery",
        formatter_class=fmt,
        description=(
            "Exemples :\n" "  xcore worker purge\n" "  xcore worker purge emails"
        ),
    )
    purge_p.add_argument(
        "queue", nargs="?", default="default", help="File à vider (défaut: default)"
    )
    _add_config(purge_p)

    # worker beat
    beat_p = worker_sub.add_parser(
        "beat",
        help="Lance Celery Beat (scheduler)",
        formatter_class=fmt,
        description=(
            "Exemples :\n"
            "  xcore worker beat\n"
            "  xcore worker beat --detach\n"
            "  xcore worker beat --schedule /tmp/beat-schedule"
        ),
    )
    _add_config(beat_p)
    _add_loglevel(beat_p)
    _add_detach(beat_p)
    beat_p.add_argument(
        "--schedule",
        default=None,
        metavar="FILE",
        help="Fichier de base de données Beat",
    )

    # ── parse & dispatch ──────────────────────────────────────────────────────
    args = parser.parse_args()

    if args.version:
        try:
            from xcore import __version__

            print(f"xcore v{__version__}")
        except ImportError:
            print("xcore (version inconnue)")
        return

    if args.command == "plugin":
        from .plugin_cmd import handle_plugin

        asyncio.run(handle_plugin(args))

    elif args.command == "sandbox":
        from .sandbox_cmd import handle_sandbox

        asyncio.run(handle_sandbox(args))

    elif args.command == "marketplace":
        from .marketplace_cmd import handle_marketplace

        asyncio.run(handle_marketplace(args))

    elif args.command == "services":
        from .plugin_cmd import handle_services

        asyncio.run(handle_services(args))

    elif args.command == "health":
        from .plugin_cmd import handle_health

        asyncio.run(handle_health(args))

    elif args.command == "worker":
        from .worker_cmd import handle_worker

        handle_worker(args)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()

"""
main.py — Point d'entrée du CLI xcore.

Installation:
    pip install xcore
    xcore --help

Commandes:
    xcore plugin list
    xcore plugin load   <name>
    xcore plugin reload <name>
    xcore plugin sign   <path> --key <secret>
    xcore plugin verify <path> --key <secret>
    xcore plugin validate <path>
    xcore services status
    xcore health
"""

from __future__ import annotations

import asyncio
import sys


def _err(msg: str) -> None:
    print(f"❌  {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"✅  {msg}")


def main() -> None:
    """Point d'entrée console_scripts."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="xcore",
        description="xcore v2 — gestion du framework plugin-first",
    )
    parser.add_argument("--config", default=None, help="Chemin vers xcore.yaml")
    parser.add_argument("--version", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    # plugin
    plugin_p = subparsers.add_parser("plugin", help="Gestion des plugins")
    plugin_sub = plugin_p.add_subparsers(dest="subcommand")
    plugin_sub.add_parser("list", help="Liste les plugins chargés")

    load_p = plugin_sub.add_parser("load", help="Charge un plugin")
    load_p.add_argument("name")

    reload_p = plugin_sub.add_parser("reload", help="Recharge un plugin")
    reload_p.add_argument("name")

    sign_p = plugin_sub.add_parser("sign", help="Signe un plugin Trusted")
    sign_p.add_argument("path")
    sign_p.add_argument("--key", default=None)

    verify_p = plugin_sub.add_parser("verify", help="Vérifie la signature d'un plugin")
    verify_p.add_argument("path")
    verify_p.add_argument("--key", default=None)

    validate_p = plugin_sub.add_parser(
        "validate", help="Valide le manifeste d'un plugin"
    )
    validate_p.add_argument("path")

    # services
    svc_p = subparsers.add_parser("services", help="État des services")
    svc_sub = svc_p.add_subparsers(dest="subcommand")
    svc_sub.add_parser("status", help="Status des services")

    # health
    subparsers.add_parser("health", help="Health check global")

    args = parser.parse_args()

    if args.version:
        from xcore import __version__

        print(f"xcore v{__version__}")
        return

    if args.command == "plugin":
        from .plugin_cmd import handle_plugin

        asyncio.run(handle_plugin(args))
    elif args.command == "services":
        from .plugin_cmd import handle_services

        asyncio.run(handle_services(args))
    elif args.command == "health":
        from .plugin_cmd import handle_health

        asyncio.run(handle_health(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

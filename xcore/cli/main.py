"""
main.py — Point d'entrée du CLI xcore.

Commandes:
    xcore plugin list
    xcore plugin load   <name>
    xcore plugin reload <name>
    xcore plugin sign   <path> --key <secret>
    xcore plugin verify <path> --key <secret>
    xcore plugin validate <path>
    xcore plugin health
    xcore plugin install <name> [--source zip|git] [--url <url>]
    xcore plugin remove  <name>
    xcore plugin info    <name>

    xcore sandbox run    <name>
    xcore sandbox limits <name>
    xcore sandbox network <name>
    xcore sandbox fs     <name>

    xcore marketplace list
    xcore marketplace trending
    xcore marketplace search <query>
    xcore marketplace show   <name>
    xcore marketplace rate   <name> --score <1-5>

    xcore services status
    xcore health
"""

from __future__ import annotations

import asyncio


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="xcore",
        description="xcore v2 — gestion du framework plugin-first",
    )
    parser.add_argument("--config", default=None, help="Chemin vers xcore.yaml")
    parser.add_argument("--version", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    # ── plugin ────────────────────────────────────────────────
    plugin_p = subparsers.add_parser("plugin", help="Gestion des plugins")
    plugin_sub = plugin_p.add_subparsers(dest="subcommand")

    plugin_sub.add_parser("list", help="Liste les plugins installés")
    plugin_sub.add_parser("health", help="Health check de tous les plugins")

    load_p = plugin_sub.add_parser(
        "load", help="Charge un plugin sur le serveur en cours"
    )
    load_p.add_argument("name")
    load_p.add_argument(
        "--host", default=None, help="Host du serveur (défaut: 127.0.0.1)"
    )
    load_p.add_argument(
        "--port", type=int, default=None, help="Port du serveur (défaut: 8000)"
    )
    load_p.add_argument(
        "--path",
        default=None,
        help="Préfixe du router ex: /app ou /plugin (défaut: plugin_prefix config)",
    )
    load_p.add_argument(
        "--key", default=None, help="API key (défaut: secret_key config)"
    )

    reload_p = plugin_sub.add_parser(
        "reload", help="Recharge un plugin sur le serveur en cours"
    )
    reload_p.add_argument("name")
    reload_p.add_argument(
        "--host", default=None, help="Host du serveur (défaut: 127.0.0.1)"
    )
    reload_p.add_argument(
        "--port", type=int, default=None, help="Port du serveur (défaut: 8000)"
    )
    reload_p.add_argument(
        "--path",
        default=None,
        help="Préfixe du router ex: /app ou /plugin (défaut: plugin_prefix config)",
    )
    reload_p.add_argument(
        "--key", default=None, help="API key (défaut: secret_key config)"
    )

    install_p = plugin_sub.add_parser("install", help="Installe un plugin")
    install_p.add_argument("name", help="Nom du plugin ou URL")
    install_p.add_argument(
        "--source",
        choices=["zip", "git", "marketplace"],
        default="marketplace",
        help="Source d'installation (défaut: marketplace)",
    )
    install_p.add_argument("--url", default=None, help="URL directe (zip ou git)")

    remove_p = plugin_sub.add_parser("remove", help="Supprime un plugin")
    remove_p.add_argument("name")

    info_p = plugin_sub.add_parser("info", help="Affiche les métadonnées d'un plugin")
    info_p.add_argument("name")

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

    # ── sandbox ───────────────────────────────────────────────
    sandbox_p = subparsers.add_parser("sandbox", help="Gestion du sandbox runtime")
    sandbox_sub = sandbox_p.add_subparsers(dest="subcommand")

    sb_run = sandbox_sub.add_parser("run", help="Lance un plugin en mode sandbox isolé")
    sb_run.add_argument("name", help="Nom du plugin")

    sb_limits = sandbox_sub.add_parser(
        "limits", help="Affiche les limites ressources d'un plugin"
    )
    sb_limits.add_argument("name")

    sb_network = sandbox_sub.add_parser(
        "network", help="Affiche la politique réseau d'un plugin"
    )
    sb_network.add_argument("name")

    sb_fs = sandbox_sub.add_parser(
        "fs", help="Affiche la politique filesystem d'un plugin"
    )
    sb_fs.add_argument("name")

    # ── marketplace ───────────────────────────────────────────
    mkt_p = subparsers.add_parser("marketplace", help="Catalogue de plugins")
    mkt_sub = mkt_p.add_subparsers(dest="subcommand")

    mkt_sub.add_parser("list", help="Liste tous les plugins du marketplace")
    mkt_sub.add_parser("trending", help="Plugins populaires")

    mkt_search = mkt_sub.add_parser("search", help="Recherche un plugin")
    mkt_search.add_argument("query")

    mkt_show = mkt_sub.add_parser("show", help="Détails d'un plugin")
    mkt_show.add_argument("name")

    mkt_rate = mkt_sub.add_parser("rate", help="Note un plugin")
    mkt_rate.add_argument("name")
    mkt_rate.add_argument("--score", type=int, choices=range(1, 6), required=True)

    # ── services ──────────────────────────────────────────────
    svc_p = subparsers.add_parser("services", help="État des services")
    svc_sub = svc_p.add_subparsers(dest="subcommand")
    svc_status_p = svc_sub.add_parser("status")
    svc_status_p.add_argument("--json", action="store_true", help="Output as JSON")

    health_p = subparsers.add_parser("health", help="Health check global")
    health_p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.version:
        from xcore import __version__

        print(f"xcore v{__version__}")
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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

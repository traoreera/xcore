"""
marketplace_cmd.py — Handlers des commandes `xcore marketplace *`.

xcore marketplace list              → liste tous les plugins
xcore marketplace trending          → plugins populaires
xcore marketplace search <query>    → recherche
xcore marketplace show   <n>     → détails complets
xcore marketplace rate   <n> --score <1-5>
"""

from __future__ import annotations

import sys


def _load_config(args):
    from xcore.configurations.loader import ConfigLoader

    return ConfigLoader.load(getattr(args, "config", None))


def _get_client(args):
    from xcore.marketplace import MarketplaceClient

    cfg = _load_config(args)
    return MarketplaceClient(cfg), cfg


async def handle_marketplace(args) -> None:
    sub = getattr(args, "subcommand", None)
    dispatch = {
        "list": _mkt_list,
        "trending": _mkt_trending,
        "search": _mkt_search,
        "show": _mkt_show,
        "rate": _mkt_rate,
    }
    handler = dispatch.get(sub)
    if handler:
        await handler(args)
    else:
        print("Usage : xcore marketplace <list|trending|search|show|rate>")


# ── list ──────────────────────────────────────────────────────


async def _mkt_list(args) -> None:
    client, _ = _get_client(args)
    print("🔍  Récupération du catalogue...")
    try:
        plugins = await client.list_plugins()
    except Exception as e:
        print(f"❌  Erreur marketplace : {e}", file=sys.stderr)
        sys.exit(1)

    if not plugins:
        print("Aucun plugin disponible.")
        return

    print(f"\n{'Nom':<25} {'Version':<10} {'Auteur':<20} {'Stars':<6} Description")
    print("─" * 85)
    for p in plugins:
        name = p.get("name", "?")[:24]
        version = p.get("version", "?")[:9]
        author = p.get("author", "?")[:19]
        stars = _stars(p.get("rating", 0))
        desc = p.get("description", "")[:30]
        print(f"  {name:<23} {version:<10} {author:<20} {stars:<6} {desc}")
    print(f"\n  Total : {len(plugins)} plugin(s)")


# ── trending ──────────────────────────────────────────────────


async def _mkt_trending(args) -> None:
    client, _ = _get_client(args)
    print("🔥  Plugins populaires...")
    try:
        plugins = await client.trending()
    except Exception as e:
        print(f"❌  Erreur marketplace : {e}", file=sys.stderr)
        sys.exit(1)

    if not plugins:
        print("Aucun plugin trending.")
        return

    print()
    for i, p in enumerate(plugins, 1):
        name = p.get("name", "?")
        version = p.get("version", "?")
        downloads = p.get("downloads", 0)
        rating = p.get("rating", 0)
        desc = p.get("description", "")
        print(
            f"  {i:>2}. {name:<25} v{version:<8} {_stars(rating)}  ⬇ {downloads:,}  {desc}"
        )


# ── search ────────────────────────────────────────────────────


async def _mkt_search(args) -> None:
    client, _ = _get_client(args)
    query = args.query
    print(f"🔍  Recherche : '{query}'...")
    try:
        results = await client.search(query)
    except Exception as e:
        print(f"❌  Erreur marketplace : {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print(f"Aucun résultat pour '{query}'.")
        return

    print(f"\n  {len(results)} résultat(s) pour '{query}' :\n")
    for p in results:
        name = p.get("name", "?")
        version = p.get("version", "?")
        author = p.get("author", "?")
        rating = p.get("rating", 0)
        desc = p.get("description", "")
        print(f"  📦  {name} v{version}  ({author})  {_stars(rating)}")
        if desc:
            print(f"      {desc}")
        print()


# ── show ──────────────────────────────────────────────────────


async def _mkt_show(args) -> None:
    client, cfg = _get_client(args)
    name = args.name
    print(f"🔍  Récupération des détails : '{name}'...")

    try:
        plugin = await client.get_plugin(name)
        versions = await client.get_versions(name)
    except Exception as e:
        print(f"❌  Erreur marketplace : {e}", file=sys.stderr)
        sys.exit(1)

    if not plugin:
        print(f"❌  Plugin '{name}' introuvable sur le marketplace.")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  📦  {plugin.get('name')}  v{plugin.get('version', '?')}")
    print(f"{'='*55}")
    print(f"  Auteur      : {plugin.get('author', '?')}")
    print(f"  Description : {plugin.get('description', '?')}")
    print(f"  Mode        : {plugin.get('execution_mode', 'legacy')}")
    print(f"  Licence     : {plugin.get('license', '?')}")
    print(
        f"  Note        : {_stars(plugin.get('rating', 0))}  ({plugin.get('rating_count', 0)} votes)"
    )
    print(f"  Téléch.     : {plugin.get('downloads', 0):,}")
    print(f"  Dépôt       : {plugin.get('repository', '?')}")

    if plugin.get("requires"):
        print(f"  Dépendances : {', '.join(plugin['requires'])}")

    if versions:
        print(f"\n  Versions disponibles ({len(versions)}) :")
        for v in versions[:5]:
            tag = " ← latest" if v.get("latest") else ""
            print(f"    {v.get('version', '?'):12}  {v.get('released_at', '?')}{tag}")
        if len(versions) > 5:
            print(f"    ... et {len(versions) - 5} autre(s)")

    print(f"\n  Pour installer :")
    print(f"    xcore plugin install {name}")
    print(f"{'='*55}\n")


# ── rate ──────────────────────────────────────────────────────


async def _mkt_rate(args) -> None:
    client, _ = _get_client(args)
    name = args.name
    score = args.score

    print(f"⭐  Notation de '{name}' : {score}/5")
    try:
        result = await client.rate_plugin(name, score)
        new_rating = result.get("new_rating", "?")
        total = result.get("rating_count", "?")
        print(
            f"✅  Note enregistrée. Nouvelle moyenne : {new_rating}/5 ({total} votes)"
        )
    except Exception as e:
        print(f"❌  Erreur : {e}", file=sys.stderr)
        sys.exit(1)


# ── helpers ───────────────────────────────────────────────────


def _stars(rating: float) -> str:
    """Convertit une note 0-5 en étoiles ASCII."""
    rating = max(0.0, min(5.0, float(rating or 0)))
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + "½" * half + "☆" * empty

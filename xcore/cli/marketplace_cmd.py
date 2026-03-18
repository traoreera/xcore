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

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


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
    with console.status("[bold green]🔍  Récupération du catalogue..."):
        try:
            plugins = await client.list_plugins()
        except Exception as e:
            console.print(f"[bold red]❌  Erreur marketplace :[/] {escape(str(e))}", file=sys.stderr)
            sys.exit(1)

    if not plugins:
        console.print("[yellow]Aucun plugin disponible.[/]")
        return

    table = Table(title=f"Catalogue Marketplace ({len(plugins)} plugins)", box=None, header_style="bold cyan")
    table.add_column("Nom", style="bold white")
    table.add_column("Version", justify="center")
    table.add_column("Auteur", style="magenta")
    table.add_column("Note", justify="center")
    table.add_column("Description", ratio=1)

    for p in plugins:
        table.add_row(
            escape(p.get("name", "?")),
            escape(p.get("version", "?")),
            escape(p.get("author", "?")),
            _stars(p.get("rating", 0)),
            escape(p.get("description", "")),
        )

    console.print(table)


# ── trending ──────────────────────────────────────────────────


async def _mkt_trending(args) -> None:
    client, _ = _get_client(args)
    with console.status("[bold orange3]🔥  Plugins populaires..."):
        try:
            plugins = await client.trending()
        except Exception as e:
            console.print(f"[bold red]❌  Erreur marketplace :[/] {escape(str(e))}", file=sys.stderr)
            sys.exit(1)

    if not plugins:
        console.print("[yellow]Aucun plugin trending.[/]")
        return

    table = Table(title="🔥  Trending Plugins", box=None, header_style="bold orange3")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Nom", style="bold white")
    table.add_column("Version")
    table.add_column("Note")
    table.add_column("Téléch.", justify="right", style="green")
    table.add_column("Description", ratio=1)

    for i, p in enumerate(plugins, 1):
        table.add_row(
            str(i),
            escape(p.get("name", "?")),
            f"v{escape(p.get('version', '?'))}",
            _stars(p.get("rating", 0)),
            f"{p.get('downloads', 0):,}",
            escape(p.get("description", "")),
        )
    console.print(table)

    console.print(table)


# ── search ────────────────────────────────────────────────────


async def _mkt_search(args) -> None:
    client, _ = _get_client(args)
    query = args.query
    with console.status(f"[bold green]🔍  Recherche : '{escape(query)}'..."):
        try:
            results = await client.search(query)
        except Exception as e:
            console.print(f"[bold red]❌  Erreur marketplace :[/] {escape(str(e))}", file=sys.stderr)
            sys.exit(1)

    if not results:
        console.print(f"[yellow]Aucun résultat pour '{escape(query)}'.[/]")
        return

    table = Table(title=f"🔍 {len(results)} résultat(s) pour '{escape(query)}'", box=None, header_style="bold green")
    table.add_column("Nom", style="bold white")
    table.add_column("Version")
    table.add_column("Auteur", style="magenta")
    table.add_column("Note")
    table.add_column("Description", ratio=1)

    for p in results:
        table.add_row(
            f"📦 {escape(p.get('name', '?'))}",
            f"v{escape(p.get('version', '?'))}",
            escape(p.get("author", "?")),
            _stars(p.get("rating", 0)),
            escape(p.get("description", "")),
        )
    console.print(table)


# ── show ──────────────────────────────────────────────────────


async def _mkt_show(args) -> None:
    client, cfg = _get_client(args)
    name = args.name
    with console.status(
        f"[bold green]🔍 Récupération de [white]{escape(name)}[/]...[/]"
    ):
        try:
            plugin = await client.get_plugin(name)
            versions = await client.get_versions(name)
        except Exception as e:
            error_console.print(f"[bold red]❌ Erreur marketplace :[/] {escape(str(e))}")
            sys.exit(1)

    if not plugin:
        error_console.print(f"[bold red]❌ Plugin '{escape(name)}' introuvable.[/]")
        sys.exit(1)

    info = [
        f"[bold cyan]Auteur      :[/][magenta] {escape(str(plugin.get('author', '?')))}[/]",
        f"[bold cyan]Description :[/] {escape(str(plugin.get('description', '?')))}",
        f"[bold cyan]Mode        :[/][yellow] {escape(str(plugin.get('execution_mode', 'legacy')))}[/]",
        f"[bold cyan]Licence     :[/][green] {escape(str(plugin.get('license', '?')))}[/]",
        f"[bold cyan]Note        :[/][bold yellow] {_stars(plugin.get('rating', 0))}[/] ({plugin.get('rating_count', 0)} votes)",
        f"[bold cyan]Téléch.     :[/][bold] {plugin.get('downloads', 0):,}[/]",
        f"[bold cyan]Dépôt       :[/][blue] {escape(str(plugin.get('repository', '?')))}[/]",
    ]
    if plugin.get("requires"):
        info.append(f"[bold cyan]Dépendances :[/] {escape(', '.join(plugin['requires']))}")

    content = "\n".join(info)
    if versions:
        content += "\n\n[bold white]Versions disponibles :[/]\n"
        for v in versions[:5]:
            tag = " [bold green]← latest[/]" if v.get("latest") else ""
            content += f"  {escape(str(v.get('version', '?'))):12} {escape(str(v.get('released_at', '?')))}{tag}\n"

    content += f"\n[italic grey70]Pour installer :[/]\n  [bold]xcore plugin install {escape(name)}[/]"
    title = f"[bold green]📦 {escape(plugin.get('name', name))} v{escape(str(plugin.get('version', '?')))}[/]"
    console.print(Panel(content, title=title, expand=False, border_style="cyan"))


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
        error_console.print(f"[bold red]❌ Erreur :[/] {escape(str(e))}")
        sys.exit(1)


# ── helpers ───────────────────────────────────────────────────


def _stars(rating: float) -> str:
    """Convertit une note 0-5 en étoiles ASCII avec markup rich."""
    try:
        val = float(rating or 0)
    except (ValueError, TypeError):
        val = 0.0
    val = max(0.0, min(5.0, val))
    full = int(val)
    half = 1 if (val - full) >= 0.5 else 0
    empty = 5 - full - half
    return f"[bold yellow]{'★' * full + '½' * half}[/]{'☆' * empty}"

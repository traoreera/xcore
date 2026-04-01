"""
sandbox_cmd.py — Handlers des commandes `xcore sandbox *`.

xcore sandbox run     <name>   → Lance un plugin en mode sandboxed isolé
xcore sandbox limits  <name>   → Affiche les limites ressources déclarées
xcore sandbox network <name>   → Affiche la politique réseau
xcore sandbox fs      <name>   → Affiche la politique filesystem
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


def _load_config(args):
    from xcore.configurations.loader import ConfigLoader

    return ConfigLoader.load(getattr(args, "config", None))


def _load_manifest(plugin_dir: Path):
    from xcore.kernel.security.validation import ManifestValidator

    return ManifestValidator().load_and_validate(plugin_dir)


async def handle_sandbox(args) -> None:
    sub = getattr(args, "subcommand", None)
    dispatch = {
        "run": _sandbox_run,
        "limits": _sandbox_limits,
        "network": _sandbox_network,
        "fs": _sandbox_fs,
    }
    handler = dispatch.get(sub)
    if handler:
        await handler(args)
    else:
        print("Usage : xcore sandbox <run|limits|network|fs> <plugin_name>")


# ── run ───────────────────────────────────────────────────────


async def _sandbox_run(args) -> None:
    """
    Lance un plugin en mode sandbox isolé (subprocess) et attend un appel ping
    pour confirmer qu'il est opérationnel.
    """
    cfg = _load_config(args)
    name = args.name
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.is_dir():
        print(f"❌  Plugin '{name}' introuvable : {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        manifest = _load_manifest(plugin_dir)
    except Exception as e:
        print(f"❌  Manifeste invalide : {e}", file=sys.stderr)
        sys.exit(1)

    from xcore.kernel.sandbox.process_manager import (
        SandboxConfig,
        SandboxProcessManager,
    )

    info = [
        f"[bold cyan]Mémoire max :[/][magenta] {manifest.resources.max_memory_mb}MB[/]",
        f"[bold cyan]Timeout     :[/][magenta] {manifest.resources.timeout_seconds}s[/]",
    ]
    title = f"[bold green]🚀 Lancement sandbox : {escape(name)}[/]"
    console.print(Panel(Group(*info), title=title, expand=False, border_style="cyan"))

    config = SandboxConfig(
        timeout=manifest.resources.timeout_seconds,
        max_restarts=manifest.runtime.retry.max_attempts,
        startup_timeout=5.0,
    )
    mgr = SandboxProcessManager(manifest, config)

    try:
        with console.status(
            f"[bold green]Démarrage de la sandbox {escape(name)}...[/]"
        ):
            await mgr.start()
            status = mgr.status()

            # Ping de confirmation
            from xcore.kernel.sandbox.ipc import IPCChannel

            resp = await mgr._channel.call("ping", {})

        if resp.success:
            console.print(f"✅ [bold green]Sandbox opérationnelle[/]")
        else:
            console.print(
                f"⚠️  [yellow]Sandbox démarrée mais ping échoué : {escape(str(resp.data))}[/]"
            )

        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_row("[bold cyan]PID   :[/]", f"[magenta]{status['pid']}[/]")
        table.add_row("[bold cyan]État  :[/]", f"[yellow]{status['state']}[/]")
        table.add_row(
            "[bold cyan]Disque:[/]",
            f"[magenta]{status['disk']['used_mb']}MB / {status['disk']['max_mb']}MB[/]",
        )
        console.print(table)

    except Exception as e:
        error_console.print(
            f"[bold red]❌ Échec démarrage sandbox :[/] {escape(str(e))}"
        )
        sys.exit(1)
    finally:
        await mgr.stop()
        console.print(f"[bold red]🛑 Sandbox {escape(name)} arrêtée.[/]")


# ── limits ────────────────────────────────────────────────────


async def _sandbox_limits(args) -> None:
    """Affiche les limites ressources déclarées dans le manifeste."""
    cfg = _load_config(args)
    name = args.name
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.is_dir():
        error_console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{escape(name)}' introuvable."
        )
        sys.exit(1)

    try:
        manifest = _load_manifest(plugin_dir)
    except Exception as e:
        error_console.print(f"[bold red]❌ Manifeste invalide :[/] {escape(str(e))}")
        sys.exit(1)

    r = manifest.resources
    rt = manifest.runtime

    info = [
        f"[bold cyan]Mémoire max      :[/][magenta] {r.max_memory_mb} MB[/]",
        f"[bold cyan]Disque max       :[/][magenta] {r.max_disk_mb} MB[/]",
        f"[bold cyan]Timeout appel    :[/][magenta] {r.timeout_seconds} s[/]",
        f"[bold cyan]Rate limit       :[/][magenta] {r.rate_limit.calls} appels / {r.rate_limit.period_seconds}s[/]",
        "\n[bold white]Runtime :[/]",
        f"  [cyan]Health check     :[/][yellow] {'activé' if rt.health_check.enabled else 'désactivé'}[/]",
    ]

    if rt.health_check.enabled:
        info.append(f"    [dim]intervalle     : {rt.health_check.interval_seconds}s[/]")
        info.append(f"    [dim]timeout        : {rt.health_check.timeout_seconds}s[/]")

    info.append(
        f"  [cyan]Retry            :[/][yellow] {rt.retry.max_attempts} tentative(s)[/]"
    )
    if rt.retry.max_attempts > 1:
        info.append(f"    [dim]backoff        : {rt.retry.backoff_seconds}s[/]")

    # Vérifie le disque actuel si le plugin est installé
    data_dir = plugin_dir / "data"
    if data_dir.exists():
        from xcore.kernel.sandbox.isolation import DiskWatcher

        watcher = DiskWatcher(data_dir, r.max_disk_mb)
        stats = watcher.stats()
        symbol = "✅" if stats["ok"] else "❌"
        info.append("\n[bold white]État actuel :[/]")
        info.append(
            f"  [cyan]Disque utilisé   :[/][magenta] {stats['used_mb']}MB / {stats['max_mb']}MB ({stats['used_pct']}%) {symbol}[/]"
        )

    content = Group(*info)
    title = f"[bold green]🛡️  Limites ressources : {escape(name)}[/]"
    console.print(Panel(content, title=title, expand=False, border_style="cyan"))


# ── network ───────────────────────────────────────────────────


async def _sandbox_network(args) -> None:
    """
    Affiche la politique réseau du plugin.
    Note : le blocage réseau actif nécessite un OS supportant les namespaces
    (Linux uniquement). Cette commande affiche l'état déclaré et détecte
    si le plugin tente des imports réseau via l'AST scan.
    """
    cfg = _load_config(args)
    name = args.name
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.is_dir():
        error_console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{escape(name)}' introuvable."
        )
        sys.exit(1)

    try:
        manifest = _load_manifest(plugin_dir)
    except Exception as e:
        error_console.print(f"[bold red]❌ Manifeste invalide :[/] {escape(str(e))}")
        sys.exit(1)

    info = []
    NETWORK_IMPORTS = {
        "socket",
        "ssl",
        "http",
        "urllib",
        "httpx",
        "requests",
        "aiohttp",
        "websockets",
    }

    from xcore.kernel.security.validation import ASTScanner

    scanner = ASTScanner()
    result = scanner.scan(plugin_dir, whitelist=manifest.allowed_imports)

    # Vérifie si des imports réseau sont dans la whitelist du plugin
    allowed_network = [i for i in manifest.allowed_imports if i in NETWORK_IMPORTS]
    blocked_by_ast = [
        e for e in result.errors if any(net in e for net in NETWORK_IMPORTS)
    ]

    if allowed_network:
        info.append(
            f"⚠️  [yellow]Imports réseau autorisés (whitelist) :[/] {escape(str(allowed_network))}"
        )
    else:
        info.append("✅ [green]Aucun import réseau autorisé[/]")

    if blocked_by_ast:
        info.append(
            "\n❌ [bold red]Imports réseau détectés et bloqués par AST scan :[/]"
        )
        for b in blocked_by_ast:
            info.append(f"   [red]→ {escape(str(b))}[/]")
    else:
        info.append("✅ [green]Aucun import réseau détecté dans le code[/]")

    info.append("\n[dim]Note : isolation réseau OS (namespaces) — Linux uniquement.[/]")
    info.append("[dim]Pour une isolation complète, utilisez un conteneur Docker.[/]")

    content = Group(*info)
    title = f"[bold green]🌐 Politique réseau : {escape(name)}[/]"
    console.print(Panel(content, title=title, expand=False, border_style="cyan"))


# ── fs ────────────────────────────────────────────────────────


async def _sandbox_fs(args) -> None:
    """Affiche et valide la politique filesystem du plugin."""
    cfg = _load_config(args)
    name = args.name
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.is_dir():
        error_console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{escape(name)}' introuvable."
        )
        sys.exit(1)

    try:
        manifest = _load_manifest(plugin_dir)
    except Exception as e:
        error_console.print(f"[bold red]❌ Manifeste invalide :[/] {escape(str(e))}")
        sys.exit(1)

    fs = manifest.filesystem
    info = []

    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column("Path", style="cyan")
    table.add_column("Status", justify="right")

    info.append("[bold white]Chemins autorisés :[/]")
    if not fs.allowed_paths:
        info.append("  [dim]Aucun chemin autorisé explicitement[/]")
    else:
        for p in fs.allowed_paths:
            abs_path = plugin_dir / p
            status = (
                "[green]✅ existe[/]"
                if abs_path.exists()
                else "[yellow]⚠️  manquant[/]"
            )
            table.add_row(escape(str(p)), status)
        info.append(table)

    if fs.denied_paths:
        info.append("\n[bold white]Chemins bloqués :[/]")
        denied_table = Table(box=None, padding=(0, 2), show_header=False)
        for p in fs.denied_paths:
            denied_table.add_row(escape(str(p)), "[red]❌ bloqué[/]")
        info.append(denied_table)

    info.append("\n[italic dim]Comportement : fail-closed[/]")
    info.append("[dim]Tout chemin hors de 'allowed' est refusé.[/]")

    content = Group(*info)
    title = f"[bold green]📁 Politique filesystem : {escape(name)}[/]"
    console.print(Panel(content, title=title, expand=False, border_style="cyan"))

    # Vérifie si le dossier data/ existe, le créer si nécessaire
    data_dir = plugin_dir / "data"
    if not data_dir.exists():
        console.print("")
        create = Confirm.ask(
            f"[yellow]⚠️  Le dossier {escape(str(data_dir.relative_to(plugin_dir.parent)))} n'existe pas. Créer ?[/]",
            default=False,
        )
        if create:
            data_dir.mkdir(parents=True)
            console.print(f"✅ [green]{data_dir} créé.[/]")

"""
plugin_cmd.py — Handlers des commandes `xcore plugin *`.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()

# Pattern pour valider le nom d'un plugin : alphanumérique, tirets et underscores uniquement.
# Cela empêche les tentatives de traversal (..) ou de chemins absolus.
PLUGIN_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_plugin_name(name: str) -> None:
    if not name or not PLUGIN_NAME_PATTERN.match(name):
        print(f"❌  Nom de plugin invalide : {name!r}")
        print("    Le nom doit contenir uniquement des lettres, chiffres, '-' et '_'.")
        sys.exit(1)


def _load_config(args):
    from xcore.configurations.loader import ConfigLoader

    return ConfigLoader.load(getattr(args, "config", None))


async def handle_plugin(args) -> None:
    sub = getattr(args, "subcommand", None)
    dispatch = {
        "list": _plugin_list,
        "health": _plugin_health,
        "load": _plugin_load,
        "reload": _plugin_reload,
        "install": _plugin_install,
        "remove": _plugin_remove,
        "info": _plugin_info,
        "sign": _plugin_sign,
        "verify": _plugin_verify,
        "validate": _plugin_validate,
    }
    handler = dispatch.get(sub)
    if handler:
        await handler(args)
    else:
        print(
            "Usage : xcore plugin <list|health|install|remove|info|load|reload|sign|verify|validate>"
        )


# ── list ──────────────────────────────────────────────────────


async def _plugin_list(args) -> None:
    cfg = _load_config(args)
    plugin_dir = Path(cfg.plugins.directory)
    if not plugin_dir.exists():
        console.print(f"[bold red]❌ Dossier plugins introuvable :[/] {plugin_dir}")
        return
    plugins = sorted(
        d.name
        for d in plugin_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )
    if not plugins:
        console.print("[yellow]Aucun plugin trouvé.[/]")
        return

    table = Table(title=f"Plugins dans {plugin_dir} ({len(plugins)})")
    table.add_column("Nom", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("Mode", style="green")
    table.add_column("Description", style="white")

    for p in plugins:
        manifest_path = plugin_dir / p / "plugin.yaml"
        if manifest_path.exists():
            try:
                import yaml

                with open(manifest_path) as f:
                    m = yaml.safe_load(f) or {}
                version = m.get("version", "?")
                mode = m.get("execution_mode", "legacy")
                desc = m.get("description", "")
                table.add_row(p, f"v{version}", mode, desc)
            except Exception:
                table.add_row(p, "[red]?[/]", "[red]?[/]", "[red]Erreur de lecture[/]")
        else:
            table.add_row(
                p,
                "[grey70]?[/]",
                "[grey70]?[/]",
                "[italic grey70]Manifeste manquant[/]",
            )

    console.print(table)


# ── health ────────────────────────────────────────────────────


async def _plugin_health(args) -> None:
    cfg = _load_config(args)
    plugin_dir = Path(cfg.plugins.directory)
    if not plugin_dir.exists():
        console.print(f"[bold red]❌ Dossier plugins introuvable :[/] {plugin_dir}")
        return

    plugins = sorted(
        d for d in plugin_dir.iterdir() if d.is_dir() and not d.name.startswith("_")
    )
    if not plugins:
        console.print("[yellow]Aucun plugin trouvé.[/]")
        return

    table = Table(title="Health Check des Plugins")
    table.add_column("Plugin", style="cyan", no_wrap=True)
    table.add_column("Mode", justify="center")
    table.add_column("Sig", justify="center")
    table.add_column("AST", justify="center")
    table.add_column("Manifest", justify="center")
    table.add_column("Status", style="dim")

    from xcore.kernel.security.signature import is_signed
    from xcore.kernel.security.validation import ASTScanner, ManifestValidator

    for plugin_dir_entry in plugins:
        name = plugin_dir_entry.name
        try:
            validator = ManifestValidator()
            manifest = validator.load_and_validate(plugin_dir_entry)

            # Signature
            signed = "✅" if is_signed(manifest) else "⚠️ "

            # AST scan
            scanner = ASTScanner()
            result = scanner.scan(plugin_dir_entry, whitelist=manifest.allowed_imports)
            ast_ok = "✅" if result.passed else "❌"

            mode = manifest.execution_mode.value
            table.add_row(name, mode, signed, ast_ok, "✅", "[green]OK[/]")

        except Exception as e:
            table.add_row(
                name,
                "[red]?[/]",
                "[red]?[/]",
                "[red]?[/]",
                "❌",
                f"[red]Erreur: {e}[/]",
            )

    console.print(table)


# ── install ───────────────────────────────────────────────────


async def _plugin_install(args) -> None:
    cfg = _load_config(args)
    source = getattr(args, "source", "marketplace")
    url = getattr(args, "url", None)
    name = args.name
    _validate_plugin_name(name)

    plugin_dir = Path(cfg.plugins.directory)
    plugin_dir.mkdir(parents=True, exist_ok=True)
    dest = plugin_dir / name

    if dest.exists():
        console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{name}' déjà installé dans {dest}"
        )
        console.print(
            f"    Pour mettre à jour : xcore plugin remove {name} && xcore plugin install {name}"
        )
        sys.exit(1)

    if source == "git" or (url and url.endswith(".git")):
        await _install_from_git(name, url or name, dest)

    elif source == "zip" or (url and (url.endswith(".zip") or url.startswith("http"))):
        if not url:
            console.print(f"[bold red]❌ Erreur :[/] --url requis pour --source zip")
            sys.exit(1)
        await _install_from_zip(name, url, dest)

    else:
        # marketplace
        from xcore.marketplace import MarketplaceClient

        client = MarketplaceClient(cfg)
        await _install_from_marketplace(client, name, dest, cfg)

    # ── Signature automatique post-install ────────────────────
    await _auto_sign(dest, cfg)

    print(f"✅  Plugin '{name}' installé dans {dest}")


async def _install_from_git(name: str, url: str, dest: Path) -> None:
    import asyncio

    print(f"📦  Clonage git : {url}")
    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--depth=1",
        url,
        str(dest),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        console.print(f"[bold red]❌ git clone échoué :[/] {stderr.decode().strip()}")
        sys.exit(1)


async def _install_from_zip(name: str, url: str, dest: Path) -> None:
    import asyncio
    import io
    import urllib.request
    import zipfile

    print(f"📦  Téléchargement : {url}")
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(url).read()
        )
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Détecte un sous-dossier racine dans le zip
            members = zf.namelist()
            prefix = members[0].split("/")[0] + "/" if "/" in members[0] else ""

            dest_resolved = dest.resolve()
            dest_resolved.mkdir(parents=True, exist_ok=True)

            for member in members:
                stripped = (
                    member[len(prefix) :]
                    if prefix and member.startswith(prefix)
                    else member
                )
                if not stripped:
                    continue

                # Protection Zip Slip: ensure target is within dest
                target = (dest_resolved / stripped).resolve()
                if not target.is_relative_to(dest_resolved):
                    print(f"⚠️  Tentative de Zip Slip ignorée : {member}")
                    continue

                if member.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(member))
    except Exception as e:
        console.print(f"[bold red]❌ Téléchargement échoué :[/] {e}")
        sys.exit(1)


async def _install_from_marketplace(client, name: str, dest: Path, cfg) -> None:
    console.print(f"🔍  Recherche '{name}' sur le marketplace...")
    plugin = await client.get_plugin(name)
    if not plugin:
        console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{name}' introuvable sur le marketplace."
        )
        sys.exit(1)

    download_url = plugin.get("download_url")
    source_type = plugin.get("source_type", "zip")

    print(
        f"📦  Plugin trouvé : v{plugin.get('version', '?')} — {plugin.get('description', '')}"
    )

    if source_type == "git":
        await _install_from_git(name, download_url, dest)
    else:
        await _install_from_zip(name, download_url, dest)


async def _auto_sign(plugin_dir: Path, cfg) -> None:
    """
    Signe automatiquement le plugin après installation
    avec la secret_key définie dans la config plugins.

    - Valide d'abord le manifeste (skip silencieux si invalide).
    - Écrit plugin.sig dans le dossier du plugin.
    - Affiche un avertissement si la clé est la valeur par défaut.
    """
    from xcore.kernel.security.signature import sign_plugin
    from xcore.kernel.security.validation import ManifestValidator

    try:
        manifest = ManifestValidator().load_and_validate(plugin_dir)
    except Exception as e:
        print(f"⚠️   Signature auto ignorée (manifeste invalide) : {e}")
        return

    secret_key = cfg.plugins.secret_key

    if secret_key in (b"change-me-in-production", b"change-me"):
        print(
            "⚠️   Signature avec la clé par défaut — "
            "définissez plugins.secret_key dans xcore.yaml pour la production."
        )

    try:
        sig_path = sign_plugin(manifest, secret_key)
        print(f"🔑  Signé automatiquement → {sig_path.name}")
    except Exception as e:
        print(f"⚠️   Signature auto échouée : {e}")


# ── remove ────────────────────────────────────────────────────


async def _plugin_remove(args) -> None:
    cfg = _load_config(args)
    name = args.name
    _validate_plugin_name(name)
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.exists():
        console.print(
            f"[bold red]❌ Erreur :[/] Plugin '{name}' introuvable dans {plugin_dir}"
        )
        sys.exit(1)

    confirm = Confirm.ask(f"[bold red]⚠️  Supprimer '{name}' ?[/]", default=False)
    if not confirm:
        console.print("Annulé.")
        return

    shutil.rmtree(plugin_dir)
    print(f"✅  Plugin '{name}' supprimé.")


# ── info ──────────────────────────────────────────────────────


async def _plugin_info(args) -> None:
    cfg = _load_config(args)
    name = args.name
    _validate_plugin_name(name)
    plugin_dir = Path(cfg.plugins.directory) / name

    if not plugin_dir.exists():
        console.print(f"[bold red]❌ Erreur :[/] Plugin '{name}' introuvable.")
        sys.exit(1)

    from xcore.kernel.security.signature import is_signed
    from xcore.kernel.security.validation import ManifestValidator

    try:
        validator = ManifestValidator()
        manifest = validator.load_and_validate(plugin_dir)
    except Exception as e:
        console.print(f"[bold red]❌ Manifeste invalide :[/] {e}")
        sys.exit(1)

    # Construction du contenu du panel
    info = [
        f"[bold cyan]Auteur      :[/][magenta] {escape(str(manifest.author))}[/]",
        f"[bold cyan]Description :[/] {escape(str(manifest.description))}",
        f"[bold cyan]Mode        :[/][yellow] {escape(str(manifest.execution_mode.value))}[/]",
        f"[bold cyan]Framework   :[/][green] {escape(str(manifest.framework_version))}[/]",
        f"[bold cyan]Entry point :[/][blue] {escape(str(manifest.entry_point))}[/]",
        f"[bold cyan]Signé       :[/] {'✅ oui' if is_signed(manifest) else '⚠️  non'}",
    ]

    if manifest.requires:
        deps = ", ".join(
            d.name if hasattr(d, "name") else str(d) for d in manifest.requires
        )
        info.append(f"[bold cyan]Dépendances :[/] {escape(deps)}")

    if manifest.allowed_imports:
        imports = ", ".join(map(str, manifest.allowed_imports))
        info.append(f"[bold cyan]Imports OK  :[/] [dim]{escape(imports)}[/]")

    # Ressources
    info.append("\n[bold white]Ressources :[/]")
    r = manifest.resources
    info.append(f"  [cyan]timeout     :[/][magenta] {r.timeout_seconds}s[/]")
    info.append(f"  [cyan]mémoire max :[/][magenta] {r.max_memory_mb}MB[/]")
    info.append(f"  [cyan]disque max  :[/][magenta] {r.max_disk_mb}MB[/]")
    info.append(
        f"  [cyan]rate limit  :[/][magenta] {r.rate_limit.calls} appels / {r.rate_limit.period_seconds}s[/]"
    )

    # Permissions
    if manifest.permissions:
        info.append(f"\n[bold white]Permissions ({len(manifest.permissions)}) :[/]")
        for p in manifest.permissions:
            effect = p.get("effect", "allow")
            symbol = "✅" if effect == "allow" else "❌"
            res = escape(str(p.get("resource", "*")))
            acts = escape(str(p.get("actions", ["*"])))
            info.append(f"  {symbol} {res} → {acts}")

    content = Group(*info)
    title = f"[bold green]🔌 {escape(manifest.name)} v{escape(manifest.version)}[/]"
    console.print(Panel(content, title=title, expand=False, border_style="cyan"))


# ── sign / verify / validate ──────────────────────────────────


async def _plugin_validate(args) -> None:
    from xcore.kernel.security.validation import ManifestValidator

    path = Path(args.path)
    if not path.exists():
        console.print(f"[bold red]❌ Erreur :[/] Dossier introuvable : {path}")
        sys.exit(1)
    try:
        v = ManifestValidator()
        manifest = v.load_and_validate(path)
        console.print(
            f"✅  Manifeste valide : {manifest.name} v{manifest.version} [{manifest.execution_mode.value}]"
        )
    except Exception as e:
        console.print(f"[bold red]❌ Manifeste invalide :[/] {e}")
        sys.exit(1)


async def _plugin_sign(args) -> None:
    from xcore.kernel.security.signature import sign_plugin
    from xcore.kernel.security.validation import ManifestValidator

    path = Path(args.path)
    key = (args.key or "change-me").encode()
    manifest = ManifestValidator().load_and_validate(path)
    sig = sign_plugin(manifest, key)
    print(f"✅  Signé : {sig}")


async def _plugin_verify(args) -> None:
    from xcore.kernel.security.signature import SignatureError, verify_plugin
    from xcore.kernel.security.validation import ManifestValidator

    path = Path(args.path)
    key = (args.key or "change-me").encode()
    manifest = ManifestValidator().load_and_validate(path)
    try:
        verify_plugin(manifest, key)
        console.print(f"✅  Signature valide : {manifest.name}")
    except SignatureError as e:
        console.print(f"[bold red]❌ Erreur de signature :[/] {e}")
        sys.exit(1)


async def _plugin_load(args) -> None:
    await _ipc_call(args, action="load", method="POST")


async def _plugin_reload(args) -> None:
    await _ipc_call(args, action="reload", method="POST")


async def _ipc_call(args, action: str, method: str = "POST") -> None:
    """
    Appelle l'API HTTP du serveur xcore en cours d'exécution.

    URL construite depuis la config :
        POST {app.host}:{app.port}{plugin_prefix}/ipc/{name}/{action}

    L'API key est lue depuis :
        1. --key en argument CLI
        2. cfg.app.secret_key (config)

    Si le serveur ne répond pas, affiche un message clair.
    """
    import asyncio
    import json
    import urllib.request
    from urllib.error import HTTPError, URLError

    cfg = _load_config(args)
    name = args.name
    _validate_plugin_name(name)

    # Construction de l'URL
    # Priorité : --host/--port/--path CLI > config > défauts
    host = getattr(args, "host", None) or getattr(cfg.app, "host", "127.0.0.1")
    port = getattr(args, "port", None) or getattr(cfg.app, "port", 8000)

    # --path : l'utilisateur donne /app ou /plugin, on complète avec /ipc/{name}/{action}
    cli_path = getattr(args, "path", None)
    base_path = cli_path or cfg.app.plugin_prefix
    base_path = "/" + base_path.strip("/")  # normalise les slashes

    url = f"http://{host}:{port}{base_path}/ipc/{name}/{action}"

    # Clé API
    cli_key = getattr(args, "key", None)
    if cli_key:
        api_key = cli_key
    else:
        sk = cfg.app.secret_key
        api_key = sk.decode("utf-8") if isinstance(sk, bytes) else sk

    print(f"🔄  {method} {url}")

    def _do_request():
        req = urllib.request.Request(
            url,
            data=b"{}",
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Plugin-Key": api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _do_request)
        status = result.get("status", "?")
        msg = result.get("msg", "")
        if status == "ok":
            console.print(f"✅  {msg or f'Plugin {name!r} : {action} OK'}")
        else:
            console.print(f"[bold red]❌ Erreur :[/] {result}")
            sys.exit(1)

    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        console.print(f"[bold red]❌ HTTP {e.code} :[/] {detail}")
        sys.exit(1)

    except URLError:
        console.print(
            f"[bold red]❌ Erreur :[/] Impossible de joindre le serveur xcore sur {host}:{port}.\n"
            f"    Vérifiez que le serveur est démarré.",
        )
        sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]❌ Erreur inattendue :[/] {e}")
        sys.exit(1)


# ── services / health globaux ─────────────────────────────────


async def handle_services(args) -> None:
    sub = getattr(args, "subcommand", None)
    if sub == "status":
        cfg = _load_config(args)
        from xcore.services import ServiceContainer

        container = ServiceContainer(cfg.services)
        await container.init()
        status = container.status()
        print(json.dumps(status, indent=2, default=str))
        await container.shutdown()


async def handle_health(args) -> None:
    cfg = _load_config(args)
    from xcore.services import ServiceContainer

    container = ServiceContainer(cfg.services)
    await container.init()
    health = await container.health()
    symbol = "✅" if health["ok"] else "❌"
    print(f"{symbol} Health : {'OK' if health['ok'] else 'DÉGRADÉ'}")
    for svc, info in health["services"].items():
        sym = "✅" if info["ok"] else "❌"
        print(f"  {sym} {svc}: {info['msg']}")
    await container.shutdown()

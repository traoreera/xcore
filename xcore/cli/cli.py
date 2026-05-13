"""
worker_cmd.py — Commandes CLI pour gérer FastAPI et Celery en processus séparés.

Commandes :
    xcore worker start            Lance API + Celery ensemble
    xcore worker start api        Lance uniquement FastAPI (uvicorn)
    xcore worker start celery     Lance uniquement le worker Celery
    xcore worker stop             Arrête tous les processus xcore
    xcore worker stop api         Arrête uniquement FastAPI
    xcore worker stop celery      Arrête uniquement Celery
    xcore worker status           État des processus en cours
    xcore worker logs             Affiche les dernières lignes de log
    xcore worker inspect          Liste les tâches et files d'attente
    xcore worker purge [queue]    Vide une file d'attente
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PID_DIR = Path(".xcore/pids")
LOG_DIR = Path("log")
PID_API = PID_DIR / "api.pid"
PID_CELERY = PID_DIR / "celery.pid"
LOG_API = LOG_DIR / "api.log"
LOG_CELERY = LOG_DIR / "celery.log"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ensure_dirs() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_pid(path: Path, pid: int) -> None:
    path.write_text(str(pid))


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def _is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _stop_pid(path: Path, label: str) -> bool:
    from rich.console import Console

    console = Console()
    pid = _read_pid(path)
    if not _is_running(pid):
        console.print(f"  [dim]{label} n'est pas en cours d'exécution[/dim]")
        path.unlink(missing_ok=True)
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            time.sleep(0.2)
            if not _is_running(pid):
                break
        else:
            os.kill(pid, signal.SIGKILL)
        path.unlink(missing_ok=True)
        console.print(f"  [green]✓[/green] {label} arrêté (PID {pid})")
        return True
    except ProcessLookupError:
        path.unlink(missing_ok=True)
        return False


def _load_config(config_path: str | None) -> Any:
    try:
        from xcore.configurations.loader import ConfigLoader

        return ConfigLoader.load(config_path)
    except Exception:
        return None


def _resolve_celery_app() -> str:
    """Retourne le chemin de l'app Celery."""
    return "xcore.services.xworker.xworker:_celery_worker"


# ── Lancement des processus ────────────────────────────────────────────────────


def _start_api(args: Any) -> subprocess.Popen | None:
    from rich.console import Console

    console = Console()

    app_path = args.app
    host = args.host
    port = args.port
    workers = getattr(args, "workers", 1)
    reload = getattr(args, "reload", False)
    log_level = args.loglevel.lower()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        app_path,
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        log_level,
    ]

    if reload:
        cmd.append("--reload")
    elif workers > 1:
        cmd.extend(["--workers", str(workers)])

    if getattr(args, "detach", False):
        _ensure_dirs()
        log_file = open(LOG_API, "a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        _write_pid(PID_API, proc.pid)
        console.print(
            f"  [green]✓[/green] API démarrée en arrière-plan — PID {proc.pid}  "
            f"[dim]log → {LOG_API}[/dim]"
        )
        return proc
    else:
        console.print(f"  [cyan]→[/cyan] API  [dim]{' '.join(cmd[2:])}[/dim]")
        return subprocess.Popen(cmd)


def _start_celery(args: Any) -> subprocess.Popen | None:
    from rich.console import Console

    console = Console()

    celery_app = _resolve_celery_app()
    queues = getattr(args, "queues", None)
    concurrency = getattr(args, "concurrency", None)
    log_level = args.loglevel.upper()

    # Charge la config pour les valeurs par défaut
    cfg = _load_config(getattr(args, "config", None))
    if cfg:
        worker_cfg = cfg.services.xworker
        if queues is None:
            queues = ",".join(worker_cfg.queues)
        if concurrency is None:
            concurrency = worker_cfg.concurrency

    if queues is None:
        queues = "default"
    if concurrency is None:
        concurrency = 4

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        celery_app,
        "worker",
        "--loglevel",
        log_level,
        "-Q",
        queues,
        "--concurrency",
        str(concurrency),
    ]

    hostname = getattr(args, "hostname", None)
    if hostname:
        cmd.extend(["-n", hostname])

    if getattr(args, "detach", False):
        _ensure_dirs()
        log_file = open(LOG_CELERY, "a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        _write_pid(PID_CELERY, proc.pid)
        console.print(
            f"  [green]✓[/green] Celery démarré en arrière-plan — PID {proc.pid}  "
            f"[dim]log → {LOG_CELERY}[/dim]"
        )
        return proc
    else:
        console.print(f"  [cyan]→[/cyan] Celery  [dim]{' '.join(cmd[2:])}[/dim]")
        return subprocess.Popen(cmd)


# ── Handlers de commandes ─────────────────────────────────────────────────────


def _cmd_start(args: Any) -> None:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    target = getattr(args, "target", "all")

    console.print(
        Panel(
            f"[bold]Démarrage xcore[/bold]  [dim]target={target}[/dim]",
            border_style="blue",
            padding=(0, 2),
        )
    )

    if target in ("all", "api"):
        api_proc = _start_api(args)
    else:
        api_proc = None

    if target in ("all", "celery"):
        celery_proc = _start_celery(args)
    else:
        celery_proc = None

    if getattr(args, "detach", False):
        return

    # Mode interactif — attend Ctrl+C et tue les deux processus proprement
    procs = [p for p in (api_proc, celery_proc) if p is not None]
    if not procs:
        return

    console.print("\n[dim]Ctrl+C pour arrêter[/dim]\n")

    try:
        # Attend que l'un des processus se termine
        while all(_is_running(p.pid) for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠[/yellow]  Arrêt en cours…")
    finally:
        for proc in procs:
            if _is_running(proc.pid):
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        console.print("[green]✓[/green]  Tous les processus arrêtés.")


def _cmd_stop(args: Any) -> None:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    target = getattr(args, "target", "all")

    console.print(
        Panel(
            f"[bold]Arrêt xcore[/bold]  [dim]target={target}[/dim]",
            border_style="red",
            padding=(0, 2),
        )
    )

    if target in ("all", "api"):
        _stop_pid(PID_API, "API")
    if target in ("all", "celery"):
        _stop_pid(PID_CELERY, "Celery")


def _cmd_status(args: Any) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()

    api_pid = _read_pid(PID_API)
    celery_pid = _read_pid(PID_CELERY)

    table = Table(title="État des processus xcore", border_style="blue", min_width=55)
    table.add_column("Service", style="bold")
    table.add_column("PID", justify="right")
    table.add_column("État")
    table.add_column("Log")

    def _status_cell(pid: int | None) -> tuple[str, str]:
        if _is_running(pid):
            return str(pid), "[green]● En cours[/green]"
        return str(pid) if pid else "—", "[dim]○ Arrêté[/dim]"

    api_pid_str, api_status = _status_cell(api_pid)
    cel_pid_str, cel_status = _status_cell(celery_pid)

    table.add_row("FastAPI (uvicorn)", api_pid_str, api_status, str(LOG_API))
    table.add_row("Celery worker", cel_pid_str, cel_status, str(LOG_CELERY))

    console.print(table)

    if getattr(args, "json", False):
        data = {
            "api": {"pid": api_pid, "running": _is_running(api_pid)},
            "celery": {"pid": celery_pid, "running": _is_running(celery_pid)},
        }
        console.print_json(json.dumps(data))


def _cmd_logs(args: Any) -> None:
    from rich.console import Console

    console = Console()
    target = getattr(args, "target", "all")
    lines = getattr(args, "lines", 50)
    follow = getattr(args, "follow", False)

    targets: list[tuple[str, Path]] = []
    if target in ("all", "api"):
        targets.append(("API", LOG_API))
    if target in ("all", "celery"):
        targets.append(("Celery", LOG_CELERY))

    if follow and len(targets) == 1:
        label, log_path = targets[0]
        if not log_path.exists():
            console.print(
                f"[yellow]⚠[/yellow]  {log_path} introuvable — le service est-il démarré ?"
            )
            return
        console.print(f"[dim]→ {log_path} (Ctrl+C pour quitter)[/dim]\n")
        try:
            proc = subprocess.Popen(["tail", "-f", "-n", str(lines), str(log_path)])
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return

    for label, log_path in targets:
        if not log_path.exists():
            console.print(f"[dim]{label}: {log_path} introuvable[/dim]\n")
            continue
        console.rule(f"[bold]{label}[/bold]  [dim]{log_path}[/dim]")
        result = subprocess.run(
            ["tail", "-n", str(lines), str(log_path)],
            capture_output=True,
            text=True,
        )
        console.print(result.stdout or "[dim](vide)[/dim]")


def _cmd_inspect(_args: Any) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()

    celery_app_path = _resolve_celery_app()
    module_path, attr = celery_app_path.rsplit(":", 1)

    try:
        import importlib

        mod = importlib.import_module(module_path)
        celery_app = getattr(mod, attr)
    except Exception as exc:
        console.print(f"[red]✗[/red]  Impossible de charger l'app Celery : {exc}")
        return

    # Tâches enregistrées
    task_table = Table(title="Tâches Celery enregistrées", border_style="blue")
    task_table.add_column("Nom", style="cyan")
    task_table.add_column("Module")

    for name, task in sorted(celery_app.tasks.items()):
        if name.startswith("celery."):
            continue
        module = getattr(task, "__module__", "—")
        task_table.add_row(name, module)

    console.print(task_table)

    # Inspection du broker (actif ou non)
    console.print()
    try:
        inspect = celery_app.control.inspect(timeout=3)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}

        if not active and not reserved:
            console.print(
                "[dim]Aucun worker actif trouvé (broker inaccessible ou aucun worker lancé)[/dim]"
            )
            return

        worker_table = Table(title="Workers actifs", border_style="green")
        worker_table.add_column("Worker")
        worker_table.add_column("Tâches actives", justify="right")
        worker_table.add_column("Tâches en attente", justify="right")

        all_workers = set(active) | set(reserved)
        for worker in sorted(all_workers):
            n_active = len(active.get(worker, []))
            n_reserved = len(reserved.get(worker, []))
            worker_table.add_row(worker, str(n_active), str(n_reserved))

        console.print(worker_table)

    except Exception as exc:
        console.print(f"[yellow]⚠[/yellow]  Broker inaccessible : {exc}")


def _cmd_purge(args: Any) -> None:
    from rich.console import Console

    console = Console()
    queue = getattr(args, "queue", None) or "default"

    celery_app_path = _resolve_celery_app()

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        celery_app_path,
        "purge",
        "-Q",
        queue,
        "-f",
    ]

    console.print(f"[yellow]⚠[/yellow]  Purge de la file [bold]{queue}[/bold]…")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"[green]✓[/green]  {result.stdout.strip() or 'File vidée.'}")
    else:
        console.print(f"[red]✗[/red]  {result.stderr.strip()}")


def _cmd_beat(args: Any) -> None:
    """Lance le scheduler Celery Beat."""
    from rich.console import Console

    console = Console()
    celery_app_path = _resolve_celery_app()
    log_level = args.loglevel.upper()

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        celery_app_path,
        "beat",
        "--loglevel",
        log_level,
    ]

    schedule = getattr(args, "schedule", None)
    if schedule:
        cmd.extend(["--schedule", schedule])

    if getattr(args, "detach", False):
        _ensure_dirs()
        pid_beat = PID_DIR / "beat.pid"
        log_beat = LOG_DIR / "beat.log"
        log_file = open(log_beat, "a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        _write_pid(pid_beat, proc.pid)
        console.print(
            f"  [green]✓[/green] Beat démarré en arrière-plan — PID {proc.pid}  "
            f"[dim]log → {log_beat}[/dim]"
        )
    else:
        console.print(f"  [cyan]→[/cyan] Beat  [dim]{' '.join(cmd[2:])}[/dim]")
        console.print("[dim]Ctrl+C pour arrêter[/dim]\n")
        try:
            proc = subprocess.Popen(cmd)
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()


# ── Point d'entrée principal ──────────────────────────────────────────────────


def handle_worker(args: Any) -> None:
    sub = getattr(args, "worker_subcommand", None)

    if sub == "start":
        _cmd_start(args)
    elif sub == "stop":
        _cmd_stop(args)
    elif sub == "status":
        _cmd_status(args)
    elif sub == "logs":
        _cmd_logs(args)
    elif sub == "inspect":
        _cmd_inspect(args)
    elif sub == "purge":
        _cmd_purge(args)
    elif sub == "beat":
        _cmd_beat(args)
    else:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title="xcore worker — commandes disponibles",
            border_style="blue",
            min_width=65,
        )
        table.add_column("Commande", style="bold cyan")
        table.add_column("Description")

        rows = [
            ("xcore worker start [api|celery]", "Lance API et/ou Celery worker"),
            ("xcore worker stop  [api|celery]", "Arrête les processus en cours"),
            ("xcore worker status", "Affiche l'état des processus"),
            ("xcore worker logs  [api|celery]", "Affiche les dernières lignes de log"),
            ("xcore worker inspect", "Liste les tâches et workers actifs"),
            ("xcore worker purge [queue]", "Vide une file d'attente Celery"),
            ("xcore worker beat", "Lance le scheduler Celery Beat"),
        ]
        for cmd, desc in rows:
            table.add_row(cmd, desc)

        console.print(table)
        console.print(
            "\n[dim]Exemple : xcore worker start --detach -Q default,emails -c 4[/dim]"
        )

"""
plugin_manager.py
──────────────────
Orchestrateur central du système de plugins.
Point d'entrée unique pour le Core FastAPI.

Usage:
    manager = PluginManager(plugins_dir="plugins", secret_key=b"...")
    await manager.load_all()
    result = await manager.call("mon_plugin", "ping", {})
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from .contracts.base_plugin import error as plugin_error
from .contracts.plugin_manifest import (
    ExecutionMode,
    ManifestError,
    PluginManifest,
    check_framework_compatibility,
    load_manifest,
)
from .sandbox.rate_limiter import RateLimiterRegistry, RateLimitExceeded
from .sandbox.scanner import ASTScanner
from .sandbox.supervisor import SandboxSupervisor, SupervisorConfig
from .trusted.runner import TrustedLoadError, TrustedRunner
from .trusted.signer import SignatureError, verify_plugin

logger = logging.getLogger("plManager")

CORE_VERSION = "1.0.0"


class PluginNotFound(Exception):
    pass


class PluginManager:
    def __init__(
        self,
        plugins_dir: str | Path,
        secret_key: bytes,
        services: dict[str, Any] | None = None,
        sandbox_config: SupervisorConfig | None = None,
        strict_trusted: bool = True,
        app: "FastAPI | None" = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._secret_key = secret_key
        self._services = services or {}
        self._sandbox_cfg = sandbox_config or SupervisorConfig()
        self._strict_trusted = strict_trusted
        self._app = app  # app FastAPI pour auto-attach des routes

        self._trusted: dict[str, TrustedRunner] = {}
        self._sandboxed: dict[str, SandboxSupervisor] = {}
        self._scanner = ASTScanner()
        self._rate = RateLimiterRegistry()

    # ──────────────────────────────────────────
    # Chargement
    # ──────────────────────────────────────────

    # ──────────────────────────────────────────
    # Tri topologique (Kahn's algorithm)
    # ──────────────────────────────────────────

    @staticmethod
    def _topo_sort(manifests: list[PluginManifest]) -> list[PluginManifest]:
        """
        Trie les manifestes selon leurs dépendances (requires).
        Garantit que erp_core est chargé avant erp_crm, etc.

        Lève ValueError si une dépendance est manquante ou si un cycle est détecté.
        Algorithme de Kahn — complexité O(N + E).
        """
        by_name = {m.name: m for m in manifests}

        # Vérification des dépendances manquantes
        for m in manifests:
            for dep in m.requires:
                if dep not in by_name:
                    raise ValueError(
                        f"[{m.name}] Dépendance introuvable : '{dep}'. "
                        f"Plugins disponibles : {list(by_name.keys())}"
                    )

        # Calcul du degré entrant (nb de dépendances non encore résolues)
        in_degree = {m.name: len(m.requires) for m in manifests}
        # Qui dépend de moi ? (graphe inversé)
        dependents: dict[str, list[str]] = {m.name: [] for m in manifests}
        for m in manifests:
            for dep in m.requires:
                dependents[dep].append(m.name)

        # File de départ = plugins sans dépendances
        queue = [m for m in manifests if in_degree[m.name] == 0]
        sorted_manifests: list[PluginManifest] = []

        while queue:
            # Stable sort : parmi les plugins prêts, ordre alphabétique
            queue.sort(key=lambda m: m.name)
            current = queue.pop(0)
            sorted_manifests.append(current)

            for dep_name in dependents[current.name]:
                in_degree[dep_name] -= 1
                if in_degree[dep_name] == 0:
                    queue.append(by_name[dep_name])

        # Si tous les manifestes ne sont pas triés → cycle détecté
        if len(sorted_manifests) != len(manifests):
            cycle_names = [
                m.name
                for m in manifests
                if m.name not in {s.name for s in sorted_manifests}
            ]
            raise ValueError(
                f"Dépendances circulaires détectées entre : {cycle_names}. "
                "Vérifie les champs 'requires' dans vos plugin.yaml."
            )

        return sorted_manifests

    # ──────────────────────────────────────────
    # Auto-attach des routes FastAPI
    # ──────────────────────────────────────────

    def _attach_routes(self, manifest: PluginManifest) -> None:
        """
        Si le plugin Trusted expose un attribut 'router' (APIRouter),
        il est automatiquement attaché à l'app FastAPI.
        Régénère le schéma OpenAPI après chaque attach.
        """
        if self._app is None:
            return
        if manifest.name not in self._trusted:
            return  # Seuls les Trusted peuvent exposer des routes

        runner = self._trusted[manifest.name]
        instance = runner._instance
        module = runner._module

        # Cherche le router sur l'instance ou sur le module
        api_router = getattr(instance, "router", None) or getattr(
            module, "router", None
        )
        if api_router is None:
            return

        try:
            self._app.include_router(api_router)
            # Force la régénération du schéma OpenAPI / Swagger
            self._app.openapi_schema = None
            logger.info(f"[{manifest.name}] 🔗 Routes attachées à FastAPI")
        except Exception as e:
            logger.error(f"[{manifest.name}] Erreur include_router : {e}")

    # ──────────────────────────────────────────
    # load_all avec tri topologique + concurrence
    # ──────────────────────────────────────────

    async def load_all(self) -> dict[str, list[str]]:
        """
        Charge tous les plugins dans l'ordre correct selon leurs dépendances.

        Pipeline :
          1. Lecture de tous les manifestes
          2. Tri topologique (résolution des requires)
          3. Chargement par vagues : les plugins d'une même vague
             (même "niveau" de dépendance) sont chargés en parallèle.
          4. Auto-attach des routes FastAPI
        """
        loaded, failed, skipped = [], [], []
        manifests: list[PluginManifest] = []

        # ── 1. Lecture des manifestes ──
        for plugin_dir in sorted(self.plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
            try:
                manifests.append(load_manifest(plugin_dir))
            except ManifestError as e:
                logger.warning(f"[{plugin_dir.name}] Manifeste invalide : {e}")
                skipped.append(plugin_dir.name)

        # ── 2. Tri topologique ──
        try:
            ordered = self._topo_sort(manifests)
        except ValueError as e:
            logger.error(f"Erreur de dépendances : {e}")
            return {
                "loaded": [],
                "failed": [m.name for m in manifests],
                "skipped": skipped,
            }

        # ── 3. Chargement par vagues ──
        # On regroupe les plugins par "niveau" : tous les plugins dont les
        # dépendances sont déjà chargées forment une vague, activée en parallèle.
        resolved: set[str] = set()

        async def _try_activate(manifest: PluginManifest) -> tuple[str, bool]:
            try:
                await self._activate(manifest)
                self._attach_routes(manifest)
                return manifest.name, True
            except Exception as e:
                logger.error(f"[{manifest.name}] Échec activation : {e}")
                return manifest.name, False

        remaining = list(ordered)
        while remaining:
            # Vague = plugins dont toutes les dépendances sont résolues
            wave = [m for m in remaining if all(dep in resolved for dep in m.requires)]
            if not wave:
                # Ne devrait pas arriver après le topo sort, mais sécurité
                stuck = [m.name for m in remaining]
                logger.error(f"Chargement bloqué — plugins en attente : {stuck}")
                failed.extend(stuck)
                break

            results = await asyncio.gather(*[_try_activate(m) for m in wave])

            for name, ok in results:
                if ok:
                    loaded.append(name)
                    resolved.add(name)
                else:
                    failed.append(name)
                    # Les plugins qui dépendaient de celui-ci sont aussi en échec
                    cascade = [
                        m.name
                        for m in remaining
                        if name in m.requires and m.name not in failed
                    ]
                    if cascade:
                        logger.error(f"[{name}] Échec en cascade sur : {cascade}")
                        failed.extend(cascade)
                        resolved.update(cascade)  # évite le blocage

            remaining = [
                m for m in remaining if m.name not in resolved and m.name not in failed
            ]

        logger.info(
            f"Plugins — chargés: {len(loaded)}, "
            f"échecs: {len(failed)}, ignorés: {len(skipped)}"
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    async def _activate(self, manifest: PluginManifest) -> None:
        if not check_framework_compatibility(manifest, CORE_VERSION):
            raise ValueError(
                f"Incompatibilité framework : plugin requiert "
                f"{manifest.framework_version}, core={CORE_VERSION}"
            )

        if manifest.execution_mode == ExecutionMode.LEGACY:
            logger.warning(
                f"[{manifest.name}] Mode LEGACY — déclarez "
                "'trusted' ou 'sandboxed' dans plugin.yaml."
            )

        # Enregistrement rate limiter
        self._rate.register(manifest.name, manifest.resources.rate_limit)

        if manifest.execution_mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY):
            await self._activate_trusted(manifest)
        elif manifest.execution_mode == ExecutionMode.SANDBOXED:
            await self._activate_sandboxed(manifest)

    async def _activate_trusted(self, manifest: PluginManifest) -> None:
        # Signature : TRUSTED toujours vérifiée, LEGACY seulement si strict_trusted
        is_trusted_mode = manifest.execution_mode == ExecutionMode.TRUSTED
        is_legacy_strict = (
            manifest.execution_mode == ExecutionMode.LEGACY and self._strict_trusted
        )

        if is_trusted_mode or is_legacy_strict:
            try:
                verify_plugin(manifest, self._secret_key)
            except SignatureError as e:
                raise TrustedLoadError(str(e))

        # ✅ Le scanner AST ne tourne PAS sur les Trusted.
        # Les Trusted sont du code signé, de confiance — les scanner est inutile
        # et génère des faux positifs (sqlalchemy, fastapi, imports internes…).
        # On logge juste un avertissement si des imports inhabituels sont présents,
        # mais ça ne bloque jamais le chargement.
        scan = self._scanner.scan_plugin(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
        )
        if not scan.passed:
            # Pour les Trusted : scan échoué = warning, pas erreur fatale
            logger.warning(
                f"[{manifest.name}] ⚠️  Scan AST (non bloquant pour Trusted) :\n{scan}"
            )
        for w in scan.warnings:
            logger.debug(f"[{manifest.name}] AST: {w}")

        runner = TrustedRunner(manifest, services=self._services)
        await runner.load()
        self._trusted[manifest.name] = runner
        logger.info(
            f"[{manifest.name}] ✅ TRUSTED | "
            f"timeout={manifest.resources.timeout_seconds}s | "
            f"rate={manifest.resources.rate_limit.calls}/"
            f"{manifest.resources.rate_limit.period_seconds}s"
        )

    async def _activate_sandboxed(self, manifest: PluginManifest) -> None:
        scan = self._scanner.scan_plugin(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
        )
        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan statique échoué :\n{scan}")
        for w in scan.warnings:
            logger.warning(f"[{manifest.name}] ⚠️  {w}")

        supervisor = SandboxSupervisor(manifest, config=self._sandbox_cfg)
        await supervisor.start()
        self._sandboxed[manifest.name] = supervisor
        logger.info(
            f"[{manifest.name}] ✅ SANDBOXED | "
            f"mem={manifest.resources.max_memory_mb}MB | "
            f"disk={manifest.resources.max_disk_mb}MB | "
            f"timeout={manifest.resources.timeout_seconds}s | "
            f"rate={manifest.resources.rate_limit.calls}/"
            f"{manifest.resources.rate_limit.period_seconds}s | "
            f"health_check={'on' if manifest.runtime.health_check.enabled else 'off'}"
        )

    # ──────────────────────────────────────────
    # Appel public avec retry + rate limit
    # ──────────────────────────────────────────

    async def call(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
    ) -> dict:
        """
        Point d'entrée unique.
        Applique : rate limiting → retry/backoff → routing Trusted/Sandbox.
        """
        # 1. Rate limiting
        try:
            await self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return plugin_error(str(e), code="rate_limit_exceeded")

        # 2. Routing avec retry
        if plugin_name in self._trusted:
            return await self._call_with_retry(
                plugin_name,
                self._trusted[plugin_name].call,
                action,
                payload,
            )

        if plugin_name in self._sandboxed:
            supervisor = self._sandboxed[plugin_name]
            if not supervisor.is_available:
                return plugin_error(
                    f"Plugin '{plugin_name}' non disponible "
                    f"(état: {supervisor.state.name})",
                    code="unavailable",
                )

            async def _sandbox_call(a, p):
                resp = await supervisor.call(a, p)
                return resp.data

            return await self._call_with_retry(
                plugin_name,
                _sandbox_call,
                action,
                payload,
            )

        return plugin_error(f"Plugin '{plugin_name}' introuvable", code="not_found")

    async def _call_with_retry(
        self,
        plugin_name: str,
        fn,
        action: str,
        payload: dict,
    ) -> dict:
        """Wrapper retry avec backoff exponentiel."""
        manifest = self._get_manifest(plugin_name)
        if manifest is None:
            return await fn(action, payload)

        retry_cfg = manifest.runtime.retry
        last_error = None
        backoff = retry_cfg.backoff_seconds

        for attempt in range(1, retry_cfg.max_attempts + 1):
            try:
                return await fn(action, payload)
            except Exception as e:
                last_error = e
                if attempt < retry_cfg.max_attempts:
                    logger.warning(
                        f"[{plugin_name}] Tentative {attempt}/"
                        f"{retry_cfg.max_attempts} échouée : {e}. "
                        f"Retry dans {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2  # backoff exponentiel

        logger.error(f"[{plugin_name}] Toutes les tentatives échouées : {last_error}")
        return plugin_error(str(last_error), code="all_retries_failed")

    def _get_manifest(self, plugin_name: str) -> PluginManifest | None:
        if plugin_name in self._trusted:
            return self._trusted[plugin_name].manifest
        if plugin_name in self._sandboxed:
            return self._sandboxed[plugin_name].manifest
        return None

    # ──────────────────────────────────────────
    # Gestion du cycle de vie
    # ──────────────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        """
        ✅ Nouveau : charge un plugin unique par nom de dossier.
        Permet l'administration dynamique sans load_all().
        """
        plugin_dir = self.plugins_dir / plugin_name
        if not plugin_dir.is_dir():
            raise PluginNotFound(f"Dossier '{plugin_dir}' introuvable")
        manifest = load_manifest(plugin_dir)
        await self._activate(manifest)

    async def unload(self, plugin_name: str) -> None:
        """
        ✅ Nouveau : décharge un plugin unique sans toucher aux autres.
        """
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].unload()
            del self._trusted[plugin_name]
            self._rate._limiters.pop(plugin_name, None)
        elif plugin_name in self._sandboxed:
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            self._rate._limiters.pop(plugin_name, None)
        else:
            raise PluginNotFound(f"Plugin '{plugin_name}' non chargé")

    async def reload(self, plugin_name: str) -> None:
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].reload()
            manifest = self._trusted[plugin_name].manifest
            self._rate.register(plugin_name, manifest.resources.rate_limit)
            # Re-attache les routes après hot-reload (le module a été réimporté)
            self._attach_routes(manifest)
        elif plugin_name in self._sandboxed:
            manifest = self._sandboxed[plugin_name].manifest
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            await self._activate_sandboxed(manifest)
            self._rate.register(plugin_name, manifest.resources.rate_limit)
        else:
            raise PluginNotFound(f"Plugin '{plugin_name}' non chargé")

    async def shutdown(self, timeout: float = 10.0) -> None:
        # ✅ Amélioration : timeout global sur le shutdown.
        # Sans timeout, un plugin dont on_unload() se bloque
        # empêche l'arrêt propre de toute l'application.
        logger.info(f"Arrêt du PluginManager (timeout={timeout}s)...")

        async def _unload_trusted(name: str, runner) -> None:
            try:
                await asyncio.wait_for(runner.unload(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"[{name}] Timeout déchargement après {timeout}s")
            except Exception as e:
                logger.error(f"[{name}] Erreur déchargement : {e}")

        async def _stop_sandbox(name: str, sup) -> None:
            try:
                await asyncio.wait_for(sup.stop(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"[{name}] Timeout arrêt sandbox après {timeout}s")
            except Exception as e:
                logger.error(f"[{name}] Erreur arrêt : {e}")

        await asyncio.gather(
            *[_unload_trusted(n, r) for n, r in self._trusted.items()],
            *[_stop_sandbox(n, s) for n, s in self._sandboxed.items()],
        )
        self._trusted.clear()
        self._sandboxed.clear()
        logger.info("PluginManager arrêté.")

    # ──────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────

    def status(self) -> dict:
        return {
            "trusted": [r.status() for r in self._trusted.values()],
            "sandboxed": [s.status() for s in self._sandboxed.values()],
        }

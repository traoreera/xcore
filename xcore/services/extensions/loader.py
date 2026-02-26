"""
loader.py — Chargeur de services tiers (extensions).

Permet de déclarer des services custom dans xcore.yaml :

    services:
      extensions:
        email:
          module: myapp.services.email:EmailService
          config:
            smtp_host: smtp.gmail.com
            smtp_port: 587
        stripe:
          module: myapp.services.payments:StripeService
          config:
            api_key: ${STRIPE_SECRET_KEY}

Le service doit hériter de BaseService ou exposer init()/shutdown()/health_check()/status().
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

from ..base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.extensions")


class ExtensionLoader(BaseService):
    name = "extensions"

    def __init__(self, config: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self._config    = config
        self.extensions: dict[str, Any] = {}

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        for name, ext_cfg in self._config.items():
            try:
                svc = self._load(name, ext_cfg)
                if hasattr(svc, "init"):
                    await svc.init()
                self.extensions[name] = svc
                logger.info(f"Extension '{name}' ✅")
            except Exception as e:
                logger.error(f"Extension '{name}' ❌ : {e}")
        self._status = ServiceStatus.READY

    def _load(self, name: str, cfg: dict) -> Any:
        module_path = cfg.get("module")
        if not module_path:
            raise ValueError(f"Extension '{name}' : 'module' obligatoire")

        module_str, _, class_str = module_path.rpartition(":")
        if not module_str:
            raise ValueError(f"Extension '{name}' : format invalide '{module_path}' (attendu module:Class)")

        module = importlib.import_module(module_str)
        cls    = getattr(module, class_str)
        ext_config = cfg.get("config", {})

        try:
            return cls(config=ext_config)
        except TypeError:
            return cls(**ext_config) if ext_config else cls()

    async def shutdown(self) -> None:
        for name, svc in self.extensions.items():
            if hasattr(svc, "shutdown"):
                try:
                    await svc.shutdown()
                except Exception as e:
                    logger.error(f"Extension '{name}' shutdown error : {e}")
        self.extensions.clear()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        results = []
        for name, svc in self.extensions.items():
            if hasattr(svc, "health_check"):
                try:
                    ok, msg = await svc.health_check()
                    results.append(f"{name}:{'ok' if ok else msg}")
                except Exception as e:
                    results.append(f"{name}:error({e})")
        if not results:
            return True, "no extensions"
        all_ok = all(":ok" in r for r in results)
        return all_ok, " | ".join(results)

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "extensions": list(self.extensions.keys()),
        }

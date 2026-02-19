"""
BaseService — contrat que chaque extension de service doit respecter.

Chaque service reçoit automatiquement :
    self.name    → nom déclaré dans le YAML  (ex: "email")
    self.config  → bloc `config:` du YAML    (ex: {"host": "smtp.gmail.com"})
    self.env     → bloc `env:` du YAML résolu (ex: {"APP_TOKEN": "abc123"})
    self.logger  → logger nommé integrations.service.<name>

Exemple dans integration.yaml :

    env_variable:
      inject: true
      env_file: ".env"

    extensions:
      mon_service:
        service: "myapp.services:MonService"
        env:
          APP_TOKEN: "${APP_TOKEN}"
          API_URL:   "${API_URL}"
        config:
          timeout: 30

Exemple dans le service :

    class MonService(BaseService):
        async def setup(self):
            token   = self.env["APP_TOKEN"]   # résolu depuis .env
            url     = self.env["API_URL"]
            timeout = self.config["timeout"]
            self.client = MonClient(url, token, timeout=timeout)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


class ServiceNotReadyError(Exception):
    """Levée si on accède à un service non initialisé."""

    pass


class BaseService:
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        env: Dict[str, str],
        registry: Any = None,
    ):
        self.name = name
        self.config = config
        self.env = env  # variables d'env résolues depuis le .env
        self.registry = registry
        self.logger = logging.getLogger(f"integrations.service.{name}")
        self._ready = False

    # ── Cycle de vie ──────────────────────────────────────────

    async def setup(self) -> None:
        """Initialisation — surcharger pour connecter des clients, etc."""
        pass

    async def teardown(self) -> None:
        """Nettoyage — surcharger pour fermer des connexions, etc."""
        pass

    def _mark_ready(self):
        self._ready = True
        self.logger.info(f"Service '{self.name}' prêt")

    def _assert_ready(self):
        if not self._ready:
            raise ServiceNotReadyError(
                f"Le service '{self.name}' n'est pas encore initialisé. "
                f"Vérifiez que Integration.init() a bien été appelé."
            )

    # ── Accès aux autres services ─────────────────────────────

    def get_service(self, name: str) -> "BaseService":
        """Récupère un autre service depuis le registre."""
        if self.registry is None:
            raise RuntimeError("Registry non disponible dans ce service.")
        return self.registry.get(name)

    # ── Représentation ────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._ready

    def __repr__(self) -> str:
        status = "ready" if self._ready else "not ready"
        return f"<{self.__class__.__name__} name='{self.name}' [{status}]>"

import crm_router as crm_router  # import absolu

hook = None


class Plugin:
    def __init__(self, services=None):
        self._services = services or {}

    async def on_load(self):
        # ── Récupère les dépendances auth depuis les services ──
        # erp_auth les a exposés dans self._services au moment de SON on_load()
        # Le tri topologique garantit que erp_auth est chargé AVANT erp_crm.

        get_current_user = self._services.get("get_current_user")
        require_roles = self._services.get("require_roles")
        global hook
        hook = self._services["Hooks"]
        if not hook:
            RuntimeError("Le service 'Hooks' est requis.")

        hook.on("plugin.auth.data", 1)(self.on_data)
        if get_current_user is None:
            raise RuntimeError(
                "Service 'get_current_user' non disponible. "
                "Vérifiez que erp_auth est dans les requires du plugin.yaml"
            )

        # ── Injecte dans le router du CRM ──
        await crm_router.app_router(get_current_user, require_roles, hook)

        await hook.emit(
            "plugin.auth.load",
            {"current_user": get_current_user, "require_role": require_roles},
        )

    @property
    def router(self):
        return crm_router.router

    async def handle(self, action: str, payload: dict) -> dict:
        return {"status": "error", "msg": f"Action inconnue : {action}"}

    async def on_data(self, event):
        print(event)


# ══════════════════════════════════════════════════════════════════
# Dans erp_crm/plugin.yaml
# ══════════════════════════════════════════════════════════════════
"""
name: erp_crm
requires:
  - erp_core
  - erp_auth    ← garantit que erp_auth est chargé avant erp_crm
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from typing_extensions import Any, Callable

router = APIRouter(prefix="/crm", tags=["ERP — CRM"])


# ── Proxies — évalués au moment de l'APPEL, pas de la définition ─
# C'est le pattern obligatoire quand la dépendance est injectée après
# la déclaration du router. Sans ça, Depends() capture None au démarrage.


# ── Routes ───────────────────────────────────────────────────────


async def app_router(get_user: Any, require_role: Any, hooks: Any):

    # Route publique — aucune auth
    @router.get("/health")
    def health():
        return {"status": "ok"}

    # Route protégée — n'importe quel utilisateur connecté
    @router.get("/contacts")
    def list_contacts(current_user=Depends(get_user)):
        return {"user": current_user.email, "contacts": []}

    # Route protégée — admin ou manager seulement
    @router.post("/contacts")
    def create_contact(
        data: dict,
        current_user=Depends(require_role("admin", "manager")),
    ):
        return {"created": True, "by": current_user.email}

    # Route protégée — admin seulement
    @router.delete("/contacts/{contact_id}")
    def delete_contact(
        contact_id: int,
        current_user=Depends(require_role("admin")),
    ):
        return {"deleted": contact_id}

    @hooks.on("plugin.auth.load", 100)
    async def testing(event):
        print(f"Event on {__name__}")

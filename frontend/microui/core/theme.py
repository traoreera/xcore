"""
Gestionnaire de thèmes DaisyUI avec cookies et middleware (VERSION CORRIGÉE)
"""

from typing import Callable, Optional

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from .config import ThemeConfigure


class ThemeManager:
    """Gère les thèmes DaisyUI pour l'application"""

    DEFAULT_THEME = "dark"
    COOKIE_NAME = "daisy_theme"
    COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 an

    @staticmethod
    def get_theme(request: Request) -> str:
        """Récupère le thème depuis les cookies"""
        return request.cookies.get(ThemeManager.COOKIE_NAME, ThemeManager.DEFAULT_THEME)
        

    @staticmethod
    def set_theme_cookie(response: Response, theme: str):
        """Définit le cookie de thème"""
        response.set_cookie(
            key=ThemeManager.COOKIE_NAME,
            value=theme,
            max_age=ThemeManager.COOKIE_MAX_AGE,
            httponly=True,  # Permettre l'accès JS si besoin
            samesite="lax",
            path="/",  # Important : disponible sur tout le site
        )


class ThemeMiddleware(BaseHTTPMiddleware):
    """Middleware pour injecter le thème dans toutes les requêtes"""

    async def dispatch(self, request: Request, call_next: Callable):
        # Récupérer le thème actuel
        theme = ThemeManager.get_theme(request)

        # Ajouter le thème au state de la requête
        request.state.theme = theme

        # Continuer le traitement
        response = await call_next(request)

        return response


def create_theme_routes(router):
    """Crée les routes pour gérer les thèmes"""

    @router.post("/theme/set")
    async def set_theme(request: Request, theme:Optional[str | None] = "light"):
        """Endpoint pour changer le thème"""
        if theme:
            theme = theme
        else:
            try:
                theme = request.form.get("theme")
            except Exception:
                theme = ThemeManager.DEFAULT_THEME

        # Créer la réponse HTML qui va recharger la page
        html = f"""
        <script>
            document.documentElement.setAttribute('data-theme', '{theme}');
            setTimeout(function() {{
                window.location.reload();
            }}, 100);
        </script>
        """

        response = HTMLResponse(content=html, status_code=200)

        # Définir le cookie
        ThemeManager.set_theme_cookie(response, theme)

        return response

    @router.get("/theme/current")
    async def get_current_theme(request: Request):
        """Endpoint pour récupérer le thème actuel"""
        theme = ThemeManager.get_theme(request)
        return {"theme": theme}


    return router


# Exemple d'utilisation dans une application Starlette
def setup_daisy_ui(app, router=None):
    """Configure DaisyUI dans l'application"""

    # Ajouter le middleware
    app.add_middleware(ThemeMiddleware)

    # Créer les routes
    if router:
        create_theme_routes(router)
        app.include_router(router)


# Helpers pour les templates Jinja2
def get_theme_context(request: Request) -> dict:
    """Retourne le contexte pour les templates"""
    return {
        "current_theme": ThemeManager.get_theme(request),
        "available_themes": ThemeConfigure.themeList,
    }


# Configuration pour le ComponentRegistry
def register_theme_helpers(env):
    """Enregistre les helpers de thème dans Jinja2"""
    env.globals.update(
        {
            "theme": lambda request: ThemeManager.get_theme(request),
            "theme_context": get_theme_context,
        }
    )

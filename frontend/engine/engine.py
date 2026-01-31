import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import httpx
import jinja2
from markupsafe import Markup, escape
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .cache import CacheManager
from .component import ComponentExtension, ComponentExtensions, auto_register_components
from .filters import (
    filter_currency,
    filter_json_pretty,
    filter_slugify,
    filter_timeago,
    filter_truncate,
)
from .globals import breadcrumbs, generate_csrf_token, paginate

logger = logging.getLogger(__name__)


class TemplateEngine:
    _instance = None

    def __init__(
        self,
        directory="templates",
        debug=True,
        cache=False,
        mfe_timeout=5.0,
        enable_minify=True,
        enable_template_cache=False,
        template_cache_ttl=300,
        template_cache: Optional[CacheManager | Any] = CacheManager,
    ):
        self.directory = directory
        self.mfe_timeout = mfe_timeout
        self.mfe_register = {}
        self.enable_minify = enable_minify
        self.enable_template_cache = enable_template_cache
        self.template_cache_ttl = template_cache_ttl

        self.template_cache = template_cache()

        self.asset_versions = {}

        # Auto-register components
        auto_register_components(f"{directory}/components")

        # Setup cache directory
        cache_dir = Path(".jinja_cache")
        cache_dir.mkdir(exist_ok=True)

        # Configure Jinja2 environment
        options = dict(
            loader=jinja2.FileSystemLoader(directory),
            auto_reload=debug,
            enable_async=True,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

        if cache:
            options["bytecode_cache"] = jinja2.FileSystemBytecodeCache(
                str(cache_dir)
            )  # type: ignore

        self.env = jinja2.Environment(**options)  # type: ignore
        self.env.add_extension(ComponentExtension)
        self.env.add_extension(ComponentExtensions)

        # Register global functions
        self.env.globals.update(
            {
                "static": self._static_url,
                "url": self._build_url,
                "render_mfe": self.render_mfe_async,
                "csrf_token": generate_csrf_token,
                "paginate": paginate,
                "breadcrumbs": breadcrumbs,
                "now": datetime.now,
            }
        )

        # Register filters
        self.env.filters.update(
            {
                "json": lambda obj: Markup(json.dumps(obj, ensure_ascii=False)),
                "json_pretty": filter_json_pretty,
                "truncate": filter_truncate,
                "slugify": filter_slugify,
                "currency": filter_currency,
                "timeago": filter_timeago,
            }
        )

    def _static_url(self, path: str):
        """Generate static URL with versioning"""
        version = self.asset_versions.get(path, "")
        if version:
            return f"/static/{path}?v={version}"
        return f"/static/{path}"

    def _build_url(self, name, **params):
        """Build URL with optional query parameters"""
        url = f"/{name}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        return url

    def _minify_html(self, html: str) -> str:
        """Simple HTML minification"""
        if not self.enable_minify:
            return html

        protected_blocks = [
            r"<svg[\s\S]*?</svg>",
            r"<path[\s\S]*?</path>",  # SVG paths
            "{{.*?}}",
        ]

        def save_block(match):
            protected_blocks.append(match.group(0))
            return f"___PROTECTED_{len(protected_blocks)-1}___"

        html = re.sub(r"<(pre|textarea|script)[\s\S]*?</\1>", save_block, html, flags=re.IGNORECASE)
        html = re.sub(r"<(pre|textarea|script)[\s\S]*?</\1>", save_block, html, flags=re.IGNORECASE)
        html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)

        # Réduire les espaces multiples (mais garder au moins un espace)
        html = re.sub(r"[ \t]+", " ", html)

        # Supprimer les espaces autour des balises (plus sûr)
        html = re.sub(r">\s+<", "><", html)

        # Supprimer les sauts de ligne inutiles
        html = re.sub(r"\n\s*\n", "\n", html)

        # Restaurer les blocs protégés
        for i, block in enumerate(protected_blocks):
            html = html.replace(f"___PROTECTED_{i}___", block)

        return html.strip()

    def _get_cache_key(self, template_name: str, ctx: dict) -> str:
        """Generate cache key for template"""
        ctx_str = json.dumps(ctx, sort_keys=True, default=str)
        key_str = f"{template_name}:{ctx_str}"
        return hashlib.sha224(key_str.encode()).hexdigest()

    async def render(
        self,
        template_name: str,
        ctx: Optional[Dict] = None,
        request: Optional[Request] = None,
        use_cache: bool = None,
    ):
        """Render a template with context"""
        ctx = ctx or {}

        # Check cache
        if use_cache is None:
            use_cache = self.enable_template_cache

        if use_cache:
            cache_key = self._get_cache_key(template_name, ctx)
            cached = self.template_cache.get(cache_key, self.template_cache_ttl)
            if cached:
                logger.debug(f"Cache hit for template: {template_name}")
                return HTMLResponse(cached)

        # Auto-detect HTMX partial requests
        if request and request.headers.get("HX-Request"):
            partial_path = f"partials/{template_name}"
            full_path = Path(self.directory) / partial_path

            if full_path.exists():
                template_name = partial_path
                logger.debug(f"Using HTMX partial: {template_name}")
        try:
            # TODO: request poluais le cache ducoup on la exclu du cache Manager
            ctx["request"] = request
            start_time = time.time()
            template = self.env.get_template(template_name)
            html = await template.render_async(**ctx)

            # Minify if enabled
            html = self._minify_html(html)

            # Cache rendered template
            if use_cache:
                self.template_cache.set(cache_key, html)

            # Log render time in debug mode
            render_time = (time.time() - start_time) * 1000
            logger.debug(f"Rendered {template_name} in {render_time:.2f}ms")

            return HTMLResponse(html)

        except jinja2.TemplateNotFound as e:
            logger.error(f"Template not found: {template_name}")
            return HTMLResponse(
                f"<h1>Template Error</h1><p>Template '{template_name}' not found</p>",
                status_code=404,
            )
        except Exception as e:
            logger.exception(f"Error rendering template '{template_name}'")
            error_html = f"""
            <h1>Template Rendering Error</h1>
            <pre>{type(e).__name__}: {str(e)}</pre>
            """
            return HTMLResponse(error_html, status_code=500)

    async def render_mfe_async(self, name: str, **kwargs):
        """Render a micro-frontend by fetching from remote URL"""
        url = self.mfe_register.get(name)

        if not url:
            logger.warning(f"MFE '{name}' not registered")
            return f"<!-- MFE '{name}' not found -->"

        try:
            async with httpx.AsyncClient(timeout=self.mfe_timeout) as client:
                response = await client.get(url, params=kwargs)
                response.raise_for_status()
                return Markup(response.text)

        except httpx.TimeoutException:
            logger.error(f"MFE '{name}' timed out after {self.mfe_timeout}s")
            return f"<!-- MFE '{name}' timeout -->"
        except httpx.HTTPError as e:
            logger.error(f"MFE '{name}' HTTP error: {e}")
            return f"<!-- MFE '{name}' error: {e} -->"
        except Exception:
            logger.exception(f"MFE '{name}' unexpected error")
            return f"<!-- MFE '{name}' error -->"

    def register_mfe(self, name: str, url: str):
        """Register a micro-frontend endpoint"""
        self.mfe_register[name] = url
        logger.info(f"Registered MFE '{name}' -> {url}")

    def register_mfes(self, mfes: Dict[str, str]):
        """Register multiple micro-frontends at once"""
        for name, url in mfes.items():
            self.register_mfe(name, url)

    def set_asset_version(self, path: str, version: str):
        """Set version for asset (cache busting)"""
        self.asset_versions[path] = version

    def add_global(self, name: str, func: Callable):
        """Add a custom global function to Jinja2"""
        self.env.globals[name] = func

    def add_filter(self, name: str, func: Callable):
        """Add a custom filter to Jinja2"""
        self.env.filters[name] = func

    def clear_cache(self):
        """Clear template cache"""
        self.template_cache.clear()
        logger.info("Template cache cleared")

    @classmethod
    def instance(cls, **kwargs):
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing)"""
        cls._instance = None

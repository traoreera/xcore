from frontend.engine import TemplateEngine
from frontend.engine.cache import CacheManager
from frontend.microui.components import *
from frontend.microui.core.theme import register_theme_helpers



engine  = TemplateEngine(
        directory="templates",
        debug=True,
        cache=False,
        mfe_timeout=5.0,
        enable_minify=True,
        enable_template_cache=False,
        template_cache_ttl=300,
        template_cache= CacheManager,
)

# register theme helpers
register_theme_helpers(env=engine.env)
from typing import Dict, Optional

from starlette.requests import Request

from .component import ComponentRegistry
from .engine import TemplateEngine


def get_engine():
    """You can also use it with `Depends`"""
    return TemplateEngine.instance()


async def render(template_name: str, ctx: Optional[Dict] = None, request: Optional[Request] = None):
    return await get_engine().render(template_name, ctx, request)


def list_templates():
    return get_engine().env.list_templates()


def register_mfe(name: str, url: str):
    """Register a micro-frontend"""
    get_engine().register_mfe(name, url)


def register_mfes(mfes: Dict[str, str]):
    """Register multiple micro-frontends"""
    get_engine().register_mfes(mfes)

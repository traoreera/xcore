from fastapi import APIRouter, Form, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# dasyUI
from frontend.config import engine
from frontend.microui.core.theme import setup_daisy_ui
from middleware.access_control_Middleware import AccessControlMiddleware
from xcore import app, events, manage, middleware, view
from xcore.appcfg import xcfg
from xcore.manage import manager

app.mount("/static", StaticFiles(directory="templates"), name="static")


# optinal middleware validation token for xcore
app.add_middleware(AccessControlMiddleware, access_rules=xcfg.cfgAcessMidlware())


router = APIRouter(tags=["dasyUI"])
setup_daisy_ui(app, router=router)


@app.get("/")
async def root():
    return await engine.render(
        "index.html", use_cache=False, request=None, ctx={"title": "Home"}
    )

@app.get("/core-docs")
async def redoc():
    return await engine.render(
        "docs/index.html", use_cache=False, request=None,
    )
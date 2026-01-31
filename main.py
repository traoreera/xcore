from middleware.access_control_Middleware import AccessControlMiddleware
from xcore import app, events, manage, middleware, view
from xcore.appcfg import xcfg
from xcore.manage import manager

# optinal middleware validation token for xcore
# app.add_middleware(AccessControlMiddleware, access_rules=xcfg.cfgAcessMidlware())


from frontend.config import engine

@app.get('/')
async def root():

    return await engine.render('index.html', use_cache=False, request=None, ctx={'title': 'Home'})
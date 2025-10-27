from middleware.access_control_Middleware import AccessControlMiddleware
from xcore import app, manage , middleware, view, events
from xcore.manage import manager
from xcore.appcfg import xcfg

# optinal middleware validation token for xcore
# app.add_middleware(AccessControlMiddleware, access_rules=xcfg.cfgAcessMidlware())

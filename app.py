"""
app.py — Exemple d'intégration complète dans FastAPI
──────────────────────────────────────────────────────
Montre comment brancher le Manager dans ton application existante.
"""

from contextlib import asynccontextmanager
from urllib import response

from fastapi import FastAPI
from xcore.sandbox.sandbox.worker import _main

from xcore.manager import Manager
from xcore.appcfg import xhooks

from integrations.routes import plugins
from integrations.routes import task
# ──────────────────────────────────────────────
# 1. Lifespan — startup / shutdown propres
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Remplace les anciens @app.on_event("startup").
    Le Manager démarre ici, s'arrête proprement à la fin.
    """
    manager: Manager = app.state.manager

    # Startup : charge tous les plugins + attache /plugin/*
    report = await manager.start()
    print(f"✅ Plugins chargés : {report['loaded']}")
    if report["failed"]:
        print(f"❌ Échecs : {report['failed']}")

    yield  # ← l'app tourne ici

    # Shutdown : arrête proprement tous les subprocesses
    await manager.stop()


# ──────────────────────────────────────────────
# 2. Création de l'app
# ──────────────────────────────────────────────

app = FastAPI(
    title="Mon API",
    lifespan=lifespan,
)


app.include_router(plugins.plugin)
app.include_router(task.task)
# Routes natives de ton Core (exemples)
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/plugins/status")
async def plugins_status():
    """Status de tous les plugins via le Manager."""
    return app.state.manager.status()


# ──────────────────────────────────────────────
# 3. Initialisation du Manager
#    (avant de créer l'app ou dans un fichier de config)
# ──────────────────────────────────────────────

# Sauvegarde des routes natives AVANT d'attacher les plugins
# (nécessaire pour le reload — on repart toujours de ces routes)
manager = Manager(
    app           = app,
    base_routes   = list(app.routes),
    plugins_dir   = "plugins",
    secret_key    = b"ejkfnwefnkejw",  # ← mettre dans .env
    services      = {
        # Services du Core injectés dans les plugins Trusted
        # "db":    db_instance,
        # "cache": cache_instance,
    },
    interval      = 2,       # secondes entre chaque check du watcher
    strict_trusted = True,   # False pour autoriser LEGACY sans signature
)

# Injecte le manager dans app.state pour qu'il soit accessible partout
app.state.manager = manager



@app.on_event("startup")
async def startup_event() -> None:
    await xhooks.emit("xcore.startup")
    await _main()
    return

@app.on_event("shutdown")
async def startup_event():
    await manager.stop()
    await xhooks.emit("xcore.shutdown")
    return
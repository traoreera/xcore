"""
app.py — Exemple d'intégration complète dans FastAPI
──────────────────────────────────────────────────────
Montre comment brancher le Manager dans ton application existante.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from integrations.db import Base, engine, get_db
from integrations.routes import plugins, task
from xcore.appcfg import xhooks
from xcore.manager import Manager

# ──────────────────────────────────────────────
# 1. Lifespan — startup / shutdown propres
# ──────────────────────────────────────────────

CORE_SERVICES = {
    "db": get_db,  # callable () → Generator[Session]
    "base": Base,  # DeclarativeBase partagé pour créer les tables
    "engine": engine,  # Engine SQLAlchemy pour create_all()
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Remplace les anciCORE_SERVICESens @app.on_event("startup").
    Le Manager démarre ici, s'arrête proprement à la fin.
    """
    from integrations.integrate import taskRuntimer

    manager: Manager = app.state.manager
    await xhooks.emit("xcore.startup")

    # Startup : charge tous les plugins + attache /plugin/*
    report = await manager.start()
    print(f"✅ Plugins chargés : {report['loaded']}")
    if report["failed"]:
        print(f"❌ Échecs : {report['failed']}")

    yield  # ← l'app tourne ici

    # Shutdown : arrête proprement tous les subprocesses
    await manager.stop()
    # taskRuntimer.on_shutdown()
    await xhooks.emit("xcore.shutdown")


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
    app=app,
    base_routes=list(app.routes),
    plugins_dir="plugins",
    secret_key=b"ejkfnwefnkejw",  # <- mettre dans .env
    services=CORE_SERVICES,
    interval=2,  # secondes entre chaque check du watcher
    strict_trusted=True,  # False pour autoriser LEGACY sans signature
)

# Injecte le manager dans app.state pour qu'il soit accessible partout
app.state.manager = manager

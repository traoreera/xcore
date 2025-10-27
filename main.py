import time
from typing import Annotated, Union

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import  CORSMiddleware
from user_agents import parse

import manager.runtimer as taskRuntimer
from admin.routes import adminrouter
from admin.service import init_root_admin
from appcfg import logger
from auth.routes import authRouter

from manager import Manager, cfg
from manager.routes.task import task
from otpprovider.routes import optProvider

app = FastAPI(title="Core API with Plugin System", version="1.0.0")
v1 = FastAPI(title="core V1", version="v1",)
v2 = FastAPI(title="core V2", version="V1.1")
# base router
v1.include_router(task)
v1.include_router(authRouter)
v1.include_router(adminrouter)
v1.include_router(optProvider)



origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]


v1.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/v1", v1)
manager = Manager(
    app=v1,
    entry_point=cfg.get("plugins", "entry_point"),
    plugins_dir=cfg.get("plugins", "directory"),
    interval=cfg.get("plugins", "interval"),
    base_routes=app.routes,
)


manager.snapshot.ignore_ext = cfg.get("snapshot", "extensions")
manager.snapshot.ignore_file = cfg.get("snapshot", "filenames")
manager.snapshot.ignore_hidden = cfg.get("snapshot", "hidden")


@app.on_event("startup")
async def startup_event():

    from database.db import get_db

    init_root_admin(next(get_db()))

    manager.run_plugins()
    taskRuntimer.on_startup()


@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_watching()
    taskRuntimer.on_shutdown()
    manager.close_db()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    print(f"Request to {request.url.path} processed in {process_time:.4f} seconds")

    return response


@app.get("/device-info")
async def get_device_info(user_agent: Annotated[Union[str, None], Header()] = None):
    """
    Récupère le type d'appareil à partir de l'en-tête User-Agent.
    """
    if user_agent:
        ua_string = user_agent
        user_agent_parsed = parse(ua_string)

        if user_agent_parsed.is_mobile:
            device_type = "Mobile"
        elif user_agent_parsed.is_tablet:
            device_type = "Tablette"
        else:
            device_type = "Ordinateur de bureau"

        return {
            "user_agent": ua_string,
            "device_type": device_type,
            "os": user_agent_parsed.os.family,
            "browser": user_agent_parsed.browser.family,
        }
    return {"message": "En-tête User-Agent non fourni"}

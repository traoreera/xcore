from typing import Annotated, Union

from fastapi import Header
from user_agents import parse

from admin.routes import adminrouter
from auth.routes import authRouter
from manager.routes.task import task
from otpprovider.routes import optProvider
from xcore import app

# all declaration base routes in xcore
app.include_router(authRouter)
app.include_router(adminrouter)
app.include_router(task)
app.include_router(optProvider)


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

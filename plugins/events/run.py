from fastapi import APIRouter, Depends

from auth import dependencies

PLUGIN_INFO = {
    "name": "Events",
    "version": "1.0.0",
    "author": "traore Eliezer",
    "Api_prefix": "/app/v1/events",
    "tag_for_identified": ["Plugin", "events"],
    "trigger": 2,
}
router = APIRouter(
    prefix=PLUGIN_INFO["Api_prefix"],
    tags=PLUGIN_INFO["tag_for_identified"],
)
second_v1 = APIRouter(prefix=PLUGIN_INFO["Api_prefix"])


class Plugin:
    def __init__(self):
        self.name = PLUGIN_INFO["name"]
        self.version = PLUGIN_INFO["version"]
        self.author = PLUGIN_INFO["author"]
        self.Api_prefix = PLUGIN_INFO["Api_prefix"]
        self.tag_for_identified = PLUGIN_INFO["tag_for_identified"]
        self.trigger = PLUGIN_INFO["trigger"]

    @router.get("/", operation_id=f"run_{PLUGIN_INFO['name']}_get")
    @staticmethod
    def run(curent_user=Depends(dependencies.get_current_user)):

        print(curent_user.email)
        return {"tag_for_identified": "trigger"}

    @router.get("/test", operation_id=f"test_{PLUGIN_INFO['name']}_get")
    @staticmethod
    async def test():

        return {"tag_for_identified": "hunt"}

    def response_model(self):
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "Api_prefix": self.Api_prefix,
            "tag_for_identified": self.tag_for_identified,
            "trigger": self.trigger,
            "add_time": ["2023-05-27", "2023-05-28", "2023-05-29"],
        }

    @router.get("/response", operation_id=f"response_{PLUGIN_INFO['name']}_get")
    @staticmethod
    def response():

        return Plugin.response_model(self := Plugin())

    @router.post("/response")
    @staticmethod
    def response(rr: str):
        print("rr >>", rr)
        return Plugin.response_model(self := Plugin())

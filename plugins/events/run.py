from fastapi import APIRouter



router = APIRouter(
    prefix="/presence",
    tags=["Presence", "Plugin"],
)


PLUGIN_INFO = {
    "name": "Presence",
    "version": "1.0.0",
    "author": "traore Eliezer",
    "Api_prefix": "/app/presence",
    "tag_for_identified": ["Plugin", "Presence"],
    "trigger": 2,
}



class Plugin:
    def __init__(self):
        self.name = PLUGIN_INFO["name"]
        self.version = PLUGIN_INFO["version"]
        self.author = PLUGIN_INFO["author"]
        self.Api_prefix = PLUGIN_INFO["Api_prefix"]
        self.tag_for_identified = PLUGIN_INFO["tag_for_identified"]
        self.trigger = PLUGIN_INFO["trigger"]
    

    @router.get("/")
    @staticmethod
    def run():
        
        return {"tag_for_identified": "trigger"}
    

    @router.get("/test")
    @staticmethod
    def test():
        
        return {"tag_for_identified": "trigger"}


    def response_model(self):
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "Api_prefix": self.Api_prefix,
            "tag_for_identified": self.tag_for_identified,
            "trigger": self.trigger,

            "add_time": ["2023-05-27","2023-05-28", "2023-05-29"],
        }


    @router.get("/response")
    @staticmethod
    def response():
        
        return Plugin.response_model(self:=Plugin())
    

    @router.post("/response")
    @staticmethod
    def response(rr:str):
        print("rr >>", rr)
        return Plugin.response_model(self:=Plugin())
from . import PLUGIN_INFO, router
from .api.author import AuthorController


class Plugin(AuthorController):

    def __init__(self):

        super(Plugin, self).__init__()
        return

    @router.get("/")
    @staticmethod
    def run():
        return []

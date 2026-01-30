from fastapi import APIRouter

PLUGIN_INFO = {
    "name": "LibraryHub",
    "version": "1.0.0",
    "author": "traore Eliezer",
    "Api_prefix": "/app/library",
    "tag_for_identified": ["Plugin", "library", "LibraryHub"],
    "trigger": 2,
}

router = APIRouter(
    prefix=PLUGIN_INFO["Api_prefix"],
    tags=PLUGIN_INFO["tag_for_identified"],
)

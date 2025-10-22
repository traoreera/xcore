from typing import Dict, Optional

from pydantic import BaseModel


class Plugin(BaseModel):
    name: str
    version: str
    author: str
    Api_prefix: str
    tag_for_identified: str
    trigger: int = 1


class Delete(BaseModel):
    name: str
    id: str


class Update(BaseModel):
    name: str
    version: str
    author: str
    Api_prefix: str
    tag_for_identified: str
    trigger: int


class TaskManager(BaseModel):
    title: str
    type: str
    module: str
    moduleDir: str
    status: Optional[bool] = True
    description: Optional[str] = ""
    version: Optional[str] = "1.0.0"
    author: Optional[str] = "Anonyme"
    metaFile: Optional[Dict] = None

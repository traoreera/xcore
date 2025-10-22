from sqlalchemy import JSON, TEXT, Boolean, Column, Integer, String

from ..db import Base
from ..schemas.plugins import TaskManager


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(30), nullable=False)
    type = Column(String(30), default="module")
    module = Column(String(30), nullable=False, unique=True)
    moduleDir = Column(String(30), default="mqtt")
    status = Column(Boolean, default=True)
    description = Column(TEXT, default="")
    version = Column(String(30), default="1.0.0")
    author = Column(String(30), default="Anonyme")
    metaFile = Column(JSON, default={})

    def __init__(self, task: TaskManager):
        self.title = task.title
        self.type = task.type
        self.module = task.module
        self.moduleDir = task.moduleDir
        self.status = task.status
        self.description = task.description
        self.version = task.version
        self.author = task.author
        self.metaFile = task.metaFile

    def ResponseModel(self):
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "module": self.module,
            "moduleDir": self.moduleDir,
            "status": self.status,
        }

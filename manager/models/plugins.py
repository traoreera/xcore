import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from manager.db import Base

from ..schemas.plugins import Plugin


class PluginsModels(Base):  # type: ignore

    __tablename__ = "plugins"
    id = Column(String(30), primary_key=True, unique=True, index=True)
    name = Column(String(30), nullable=False)
    version = Column(String(30), nullable=False, default="V0.0.0")
    author = Column(String(30), nullable=False)
    Api_prefix = Column(String(30), nullable=False)
    tag_for_identified = Column(String(30), nullable=False)
    trigger = Column(Integer, nullable=False, default=1)
    add_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    active = Column(Boolean, default=True)

    def __init__(self, plugin: Plugin):
        self.id = str(uuid.uuid4())[:30]
        self.name = plugin.name
        self.version = plugin.version
        self.author = plugin.author
        self.Api_prefix = plugin.Api_prefix
        self.tag_for_identified = plugin.tag_for_identified
        self.trigger = plugin.trigger

    def response_model(self):
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "Api_prefix": self.Api_prefix,
            "tag_for_identified": self.tag_for_identified,
            "trigger": self.trigger,
            "add_time": self.add_time,
            "update_time": self.update_time,
            "active": self.active,
        }

    def response(self):
        return {
            "name": self.name,
            "Api_prefix": self.Api_prefix,
            "tag_for_identified": self.tag_for_identified,
            "active": self.active,
        }

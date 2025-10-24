from pydantic import BaseModel, Field, RootModel


class TaskResource(BaseModel):
    tid: int = Field(..., description="ID du thread")
    cpu_time: float = Field(..., description="Temps CPU total en secondes")
    duration: float = Field(..., description="Durée d'exécution en secondes")
    memory_mb: float = Field(..., description="Mémoire utilisée (Mo)")
    retrying: int = Field(..., description="Nombre de tentatives de redémarrage")

    class Config:
        orm_mode = True


class TaskResourcesResponse(RootModel[dict[str, TaskResource]]):

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]

    def dict(self, *args, **kwargs):
        return self.root


class TaskStatusResponse(BaseModel):
    name: str = Field(..., description="Nom du service")
    status: str = Field(..., description="Etat du service")


class TaskListResponse(BaseModel):
    tasks: list


class RestartService(TaskStatusResponse):
    class Config:
        orm_mode = True

    success: bool = Field(..., description="Etat de la command")

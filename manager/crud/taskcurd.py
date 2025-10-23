import importlib.util
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..db import get_db
from ..models.tasks import TaskModel
from ..plManager import logger
from ..schemas.plugins import TaskManager

core_task_threads = []


class ModuleRuntimeManager:
    def __init__(self, module_dir: str = "backgroundtasks"):
        """
        Initialize ModuleRuntimeManager.

        Initialize the ModuleRuntimeManager with a given database session and module directory.

        :param db: SQLAlchemy Session object, required
        :param module_dir: str, default="backgroundtasks"
        """
        self.db: Session = next(get_db())

        # Resolve the module directory to its absolute path
        self.module_dir: Path = Path(module_dir).resolve()
        if not os.path.exists(self.module_dir):
            os.makedirs(self.module_dir, exist_ok=True)
        # If the module directory is not already in sys.path, add it
        if str(self.module_dir.parent) not in sys.path:
            sys.path.insert(0, str(self.module_dir.parent))

        # Register all modules in the directory
        self.register_new_modules()

        # Start watching the directory for new modules
        self.start_watching()

    def get_all_python_modules(self):
        """
        Return a list of all Python modules in the module directory.

        This function returns a list of all Python modules (i.e. files with a .py extension)
        in the module directory, excluding modules that start with "__".

        :return: list[str]
        """
        # Exclude modules that start with "__" to avoid importing internal modules
        # Use glob to find all files with a .py extension in the module directory
        # Use the stem attribute of the Path object to get the module name (without the extension)
        return [
            f.stem for f in self.module_dir.glob("*.py") if not f.name.startswith("__")
        ]

    def extract_metadata(self, module_name: str) -> dict:
        """
        Extract the metadata of a given module.

        This function tries to import the given module, executes it, and returns
        the metadata of the module if it exists. If the module does not exist,
        or if there is an error executing the module, an empty dictionary is returned.

        :param module_name: str, the name of the module to extract metadata from
        :return: dict, the metadata of the module, or an empty dictionary if an error occurs
        """
        try:
            # Resolve the file path of the module
            module_path = self.module_dir / f"{module_name}.py"
            # Get the spec of the module
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            # Create the module from the spec
            module = importlib.util.module_from_spec(spec)  # type: ignore
            # Execute the module
            spec.loader.exec_module(module)  # type: ignore
            # Return the metadata of the module
            return (
                getattr(module, "metadata", {}) if hasattr(module, "metadata") else {}
            )
        except Exception as e:
            # Log an error if an exception occurs
            logger.error(f"Erreur d'execution de la tache {module_name}")
            logger.exception(e)
            # Return an empty dictionary if an error occurs
            return {}

    def register_new_modules(self):
        """
        Register all new modules found in the module directory.

        This function iterates over all files with a .py extension in the module directory,
        excludes internal modules (those that start with "__"), and registers all new modules
        that it finds. For each new module, it extracts the metadata of the module,
        and creates a new instance of `TaskManager` with the extracted metadata.
        The new instance is then added to the database using `add_task()`.

        :return: None
        """
        modules = self.get_all_python_modules()
        existing_names = [
            task.module
            for task in self.db.query(TaskModel).with_entities(TaskModel.module).all()
        ]
        new_modules = [m for m in modules if m not in existing_names]

        # Iterate over all new modules and register them
        for module_name in new_modules:
            meta: dict = self.extract_metadata(module_name)

            # Initialize the metadata with default values
            defaults = {}
            for key, value in meta.items():
                if key in [
                    "title",
                    "type",
                    "moduleDir",
                    "description",
                    "version",
                    "author",
                    "con",
                ]:
                    pass
                else:
                    # Remove the deprecated "con" key if it exists
                    if key == "con":
                        continue
                    defaults[key] = value

            try:
                task = TaskManager(
                    title=meta.get("title", module_name),
                    type=meta["type"],
                    module=module_name,
                    moduleDir=str(meta["moduleDir"]),
                    status=True,
                    description=meta["description"],
                    version=meta["version"],
                    author=meta["author"],
                    metaFile=defaults,  # enregistre toutes les métadonnées en JSON
                )
                self.add_task(task=task)
                logger.info(f" Nouveau module détecté : {module_name}:")
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout du module {module_name} : {e}")
                continue

        logger.info(
            f"Modules enregistrés : {[m.title for m in self.get_enabled_modules()]}"
        )

    def add_task(self, task: TaskManager):
        try:
            logger.info(f"Ajout de la tache {task.title}")
            return self.__save_task(task)
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Erreur ajout {task.title} : {e}")
            return None

    def __save_task(self, task: TaskManager):
        try:
            self.db.add(TaskModel(task=task))
            self.db.commit()
            # self.db.refresh(task)
            logger.info(f"Tache {task.title} ajoutée avec succès.")
            return task
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors de l'ajout de la tache {task.title} : {e}")
            return None

    def get_enabled_modules(self):
        return self.db.query(TaskModel).filter(TaskModel.status).all()

    def load_module_target(self, module_name):
        try:
            module_path = self.module_dir / f"{module_name}.py"
            logger.info(f"Chargement du module {module_name}.")
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "service_main"):

                if module.metadata:
                    try:
                        logger.info(f"Module {module_name} chargé.")
                        if responses := module.metadata.get("con"):
                            core_task_threads.extend(responses)
                    except Exception as e:
                        logger.warning(f"Erreur chargement {module_name} : {e}")
                return module.service_main
            logger.error(f"{module_name} ne contient pas de service_main()")
            return None
        except Exception as e:
            logger.error(f"Erreur chargement {module_name} : {e}")
            return None

    def list_tasks(self):
        return [task.ResponseModel() for task in self.db.query(TaskModel).all()]

    def start_watching(self):
        class ModuleWatcher(FileSystemEventHandler):
            def __init__(self, outer):
                self.outer = outer

            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".py"):
                    return
                module_name = Path(event.src_path).stem
                logger.info(f"Nouveau fichier détecté : {module_name}")
                self.outer.register_new_modules()
                self.outer.load_module_target(module_name)

        observer = Observer()
        observer.schedule(ModuleWatcher(self), str(self.module_dir), recursive=False)
        observer.daemon = True
        observer.start()
        logger.info(f"🛡️ Surveillance du dossier '{self.module_dir}' activée.")

    def start_module(
        self,
        module_name: str,
    ):

        if (
            mod := self.db.query(TaskModel)
            .filter(TaskModel.module == module_name)
            .first()
        ):
            return self.load_module_target(mod.module)
        return None

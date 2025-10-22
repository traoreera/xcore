#!/usr/bin/env python3
"""
Automatic model discovery system for database migrations
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .import logger, cfg


class ModelDiscovery:
    """Système de découverte automatique des modèles SQLAlchemy"""

    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.discovered_models = {}
        self.base_classes = set()

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier JSON"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"✅ Configuration chargée depuis {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"❌ Fichier de configuration non trouvé: {config_path}")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur lors du parsing JSON: {e}")
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut"""
        return {
            "migration": {
                "auto_discover_models": True,
                "model_discovery": {
                    "plugins_path": "plugins",
                    "exclude_directories": ["__pycache__", ".git"],
                    "include_file_patterns": ["*.py"],
                    "exclude_file_patterns": ["__init__.py", "test_*.py"],
                },
            },
        }

    def find_python_files(self, directory: str) -> List[str]:
        """Trouve tous les fichiers Python dans un répertoire"""
        python_files = []
        directory_path = Path(directory)

        if not directory_path.exists():
            logger.warning(f"⚠️ Répertoire non trouvé: {directory}")
            return python_files

        exclude_dirs = self.config["migration"]["model_discovery"][
            "exclude_directories"
        ]
        exclude_patterns = self.config["migration"]["model_discovery"][
            "exclude_file_patterns"
        ]

        for file_path in directory_path.rglob("*.py"):
            # Vérifier si le fichier est dans un répertoire exclu
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            # Vérifier si le fichier correspond aux patterns exclus
            if any(file_path.match(pattern) for pattern in exclude_patterns):
                continue

            python_files.append(str(file_path))

        return python_files

    def discover_all_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Découvre tous les modèles dans l'application"""
        all_models = {"core_models": [], "plugin_models": {}}

        # Découvrir les modèles core
        core_paths = cfg.get("automigration", 'models')
        for core_path in core_paths:
            if os.path.exists(core_path):
                core_files = self.find_python_files(core_path)
                for file_path in core_files:
                    models = self.analyze_python_file(file_path)
                    all_models["core_models"].extend(models)
                    logger.info(f"📋 Trouvé {len(models)} modèles dans {file_path}")

        return all_models

    def analyze_python_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyse un fichier Python pour trouver les modèles SQLAlchemy"""
        models = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Recherche simple par patterns
            if "class " in content and ("Base" in content or "deps.Base" in content):
                lines = content.split("\n")
                current_class = None
                table_name = None

                for line in lines:
                    line = line.strip()

                    # Détection de classe
                    if line.startswith("class ") and (
                        "(Base)" in line or "(deps.Base)" in line
                    ):
                        if current_class and table_name:
                            models.append(
                                {
                                    "class_name": current_class,
                                    "table_name": table_name,
                                    "file_path": file_path,
                                    "module_path": self.file_path_to_module_path(
                                        file_path
                                    ),
                                }
                            )

                        current_class = line.split("(")[0].replace("class ", "").strip()
                        table_name = None

                    # Détection de __tablename__
                    elif "__tablename__" in line and "=" in line:
                        table_name = line.split("=")[1].strip().strip("\"'")

                # Ajouter la dernière classe trouvée
                if current_class and table_name:
                    models.append(
                        {
                            "class_name": current_class,
                            "table_name": table_name,
                            "file_path": file_path,
                            "module_path": self.file_path_to_module_path(file_path),
                        }
                    )

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse de {file_path}: {e}")

        return models

    def file_path_to_module_path(self, file_path: str) -> str:
        """Convertit un chemin de fichier en chemin de module Python"""
        module_path = file_path.replace("/", ".").replace("\\", ".")
        if module_path.endswith(".py"):
            module_path = module_path[:-3]

        if module_path.startswith("./"):
            module_path = module_path[2:]
        elif module_path.startswith("."):
            module_path = module_path[1:]

        return module_path

    def generate_import_statements(self, models_data: Dict[str, Any]) -> List[str]:
        """Génère les déclarations d'import pour tous les modèles découverts"""
        imports = []

        # Imports des modèles core
        for model in models_data["core_models"]:
            module_path = model["module_path"]
            class_name = model["class_name"]
            imports.append(f"from {module_path} import {class_name}")

        # Imports des modèles plugins
        for plugin_name, plugin_models in models_data["plugin_models"].items():
            for model in plugin_models:
                module_path = model["module_path"]
                class_name = model["class_name"]
                imports.append(f"from {module_path} import {class_name}")

        return list(set(imports))

    def generate_model_summary(self, models_data: Dict[str, Any]) -> str:
        """Génère un résumé des modèles découverts"""
        summary = []
        summary.append("🔍 RÉSUMÉ DE LA DÉCOUVERTE DE MODÈLES")
        summary.append("=" * 50)

        # Modèles core
        core_count = len(models_data["core_models"])
        summary.append(f"📋 Modèles Core: {core_count}")
        for model in models_data["core_models"]:
            table_name = model["table_name"] or "N/A"
            summary.append(f"   - {model['class_name']} -> {table_name}")

        # Modèles plugins
        plugin_count = sum(
            len(models) for models in models_data["plugin_models"].values()
        )
        summary.append(f"\n🔌 Modèles Plugins: {plugin_count}")

        for plugin_name, plugin_models in models_data["plugin_models"].items():
            summary.append(f"   Plugin '{plugin_name}': {len(plugin_models)} modèles")
            for model in plugin_models:
                table_name = model["table_name"] or "N/A"
                summary.append(f"     - {model['class_name']} -> {table_name}")

        summary.append(f"\n📊 Total: {core_count + plugin_count} modèles découverts")

        return "\n".join(summary)


def main():
    """Fonction principale"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Découverte automatique de modèles SQLAlchemy"
    )
    parser.add_argument(
        "--config", default="config.json", help="Chemin du fichier de configuration"
    )
    parser.add_argument(
        "--output", default="discovered_models.json", help="Fichier de sortie"
    )
    parser.add_argument("--summary", action="store_true", help="Afficher un résumé")
    parser.add_argument(
        "--imports", action="store_true", help="Générer les déclarations d'import"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # Initialiser le système de découverte
    discovery = ModelDiscovery(args.config)

    # Découvrir tous les modèles
    print("🔍 Démarrage de la découverte de modèles...")
    models_data = discovery.discover_all_models()

    # Sauvegarder les résultats
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(models_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats sauvegardés dans {args.output}")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")

    # Afficher le résumé si demandé
    if args.summary:
        summary = discovery.generate_model_summary(models_data)
        print(f"\n{summary}")

    # Générer les imports si demandé
    if args.imports:
        imports = discovery.generate_import_statements(models_data)
        print(f"\n📦 DÉCLARATIONS D'IMPORT:")
        print("=" * 30)
        for imp in imports:
            print(imp)

    print(f"\n✅ Découverte terminée!")


if __name__ == "__main__":
    main()

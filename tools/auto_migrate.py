#!/usr/bin/env python3
"""
Script de migration automatique avec découverte des modèles
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List

from . import cfg, logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AutoMigrationManager:
    """Gestionnaire de migration automatique avec découverte de modèles"""

    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.discovered_models = self.discover_models()

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut"""
        return {
            "migration": {"auto_discover_models": True},
            "plugins": {"enabled": True},
        }

    def discover_models(self) -> Dict[str, List[str]]:
        """Découvre tous les modèles dans l'application"""
        models = {"core_models": [], "plugin_models": []}

        # Découvrir les modèles core

        for model in cfg.get("automigration", "models"):
            if os.path.exists(model):
                for root, dirs, files in os.walk(model):
                    for file in files:
                        if file.endswith(".py") and file != "__init__.py":
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    if self.contains_sqlalchemy_model(content):
                                        models["core_models"].append(file_path)
                                        logger.info(
                                            f"📋 Core model trouvé: {file_path}"
                                        )
                            except Exception as e:
                                logger.warning(f"⚠️ Erreur lecture {file_path}: {e}")

        # Découvrir les modèles plugins
        if os.path.exists("plugins") and self.config.get("plugins", {}).get(
            "enabled", True
        ):
            for plugin_dir in os.listdir("plugins"):
                plugin_path = os.path.join("plugins", plugin_dir)
                if os.path.isdir(plugin_path) and not plugin_dir.startswith("__"):
                    for root, dirs, files in os.walk(plugin_path):
                        for file in files:
                            if file.endswith(".py") and file != "__init__.py":
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        content = f.read()
                                        if self.contains_sqlalchemy_model(content):
                                            models["plugin_models"].append(file_path)
                                            logger.info(
                                                f"🔌 Plugin model trouvé: {file_path}"
                                            )
                                except Exception as e:
                                    logger.warning(f"⚠️ Erreur lecture {file_path}: {e}")

        return models

    def contains_sqlalchemy_model(self, content: str) -> bool:
        """Vérifie si le contenu contient des modèles SQLAlchemy"""
        return "class " in content and (
            "(Base)" in content
            or "(deps.Base)" in content
            or "__tablename__" in content
        )

    def generate_env_py_imports(self) -> str:
        """Génère les imports pour env.py"""
        imports = []

        # Imports des modèles découverts
        all_files = (
            self.discovered_models["core_models"]
            + self.discovered_models["plugin_models"]
        )

        for file_path in all_files:
            try:
                # Convertir le chemin en import Python
                module_path = (
                    file_path.replace("/", ".").replace("\\", ".").replace(".py", "")
                )

                # Lire le fichier pour extraire les noms de classes
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Recherche simple des classes qui héritent de Base
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("class ") and (
                        "(Base)" in line
                        or "(target_metadata = data.Base.metadata)" in line
                    ):
                        class_name = line.split("(")[0].replace("class ", "").strip()
                        imports.append(
                            f"from {module_path.removeprefix('..')} import {class_name}"
                        )

            except Exception as e:
                logger.warning(f"⚠️ Erreur génération import pour {file_path}: {e}")

        return "\n".join(sorted(set(imports)))

    def update_env_py(self):
        """Met à jour le fichier env.py avec les imports découverts"""
        env_path = "alembic/env.py"

        if not os.path.exists(env_path):
            logger.error(f"❌ Fichier {env_path} non trouvé")
            return False

        try:
            # Générer les imports
            imports = self.generate_env_py_imports()

            # Lire le fichier existant
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Chercher la section d'imports automatiques
            marker_start = "# AUTO-GENERATED IMPORTS START"
            marker_end = "# AUTO-GENERATED IMPORTS END"

            if marker_start in content and marker_end in content:
                # Remplacer la section existante
                start_idx = content.find(marker_start)
                end_idx = content.find(marker_end) + len(marker_end)

                new_section = f"{marker_start}\n{imports}\n{marker_end}"
                new_content = content[:start_idx] + new_section + content[end_idx:]
            else:
                # Ajouter la section avant la configuration des métadonnées
                target_line = "target_metadata = Base.metadata"
                if target_line in content:
                    new_imports_section = (
                        f"\n{marker_start}\n{imports}\n{marker_end}\n\n"
                    )
                    new_content = content.replace(
                        target_line, new_imports_section + target_line
                    )
                else:
                    logger.warning("⚠️ Impossible de trouver où insérer les imports")
                    return False

            # Écrire le fichier mis à jour
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info("✅ Fichier env.py mis à jour avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour de env.py: {e}")
            return False

    def print_summary(self):
        """Affiche un résumé de la découverte"""
        core_count = len(self.discovered_models["core_models"])
        plugin_count = len(self.discovered_models["plugin_models"])
        total = core_count + plugin_count

        print(f"\n🔍 RÉSUMÉ DE LA DÉCOUVERTE AUTOMATIQUE")
        print("=" * 50)
        print(f"📋 Modèles Core trouvés: {core_count}")
        for model_file in self.discovered_models["core_models"]:
            print(f"   - {model_file}")

        print(f"\n🔌 Modèles Plugin trouvés: {plugin_count}")
        for model_file in self.discovered_models["plugin_models"]:
            print(f"   - {model_file}")

        print(f"\n📊 Total: {total} fichiers de modèles découverts")

        return total > 0


def main():
    """Fonction principale"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migration automatique avec découverte de modèles"
    )
    parser.add_argument(
        "--config", default="config.json", help="Fichier de configuration"
    )
    parser.add_argument(
        "--update-env", action="store_true", help="Mettre à jour env.py"
    )
    parser.add_argument("--summary", action="store_true", help="Afficher le résumé")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # Initialiser le gestionnaire
    print("🚀 Démarrage de la migration automatique...")
    manager = AutoMigrationManager(args.config)

    # Afficher le résumé si demandé
    if args.summary:
        models_found = manager.print_summary()
        if not models_found:
            print("⚠️ Aucun modèle trouvé!")
            return

    # Mettre à jour env.py si demandé
    if args.update_env:
        print("\n🔧 Mise à jour du fichier env.py...")
        success = manager.update_env_py()
        if success:
            print("✅ Mise à jour réussie!")
        else:
            print("❌ Échec de la mise à jour")
            sys.exit(1)

    print("\n✅ Migration automatique terminée!")


if __name__ == "__main__":
    main()

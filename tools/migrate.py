#!/usr/bin/env python3
"""
Database Migration Script for FastHTML App

This script provides comprehensive database migration management using Alembic.
It handles schema creation, updates, rollbacks, and migration status checking.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import create_engine, text

    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from data import Base

    from .import logger,cfg
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("📦 Please install required dependencies: pip install alembic sqlalchemy")
    sys.exit(1)



class MigrationManager:
    """Gestionnaire de migrations pour core"""

    def __init__(self, config_path: str = "alembic.ini"):
        self.config_path = config_path
        self.alembic_cfg = None
        self.setup_alembic_config()

    def setup_alembic_config(self):
        """Configure Alembic"""
        try:
            self.alembic_cfg = Config(self.config_path)
            logger.info(f"✅ Configuration Alembic chargée depuis {self.config_path}")
        except Exception as e:
            logger.error(
                f"❌ Erreur lors du chargement de la configuration Alembic: {e}"
            )
            raise

    def get_database_url(self) -> str:
        """Récupère l'URL de la base de données"""
        try:
            

            url = cfg.get("database", "url")
            logger.info(f"🔗 URL de base de données récupérée: {url[:10]}***")
            return url
        except:
            # Fallback vers les variables d'environnement
            url = None
            logger.warning(f"⚠️  Utilisation de l'URL par défaut: {url[:10]}***")
            return url

    def create_initial_migration(self, message: str = "Initial migration") -> bool:
        """Crée la migration initiale"""
        try:
            logger.info("🚀 Création de la migration initiale...")

            # Mettre à jour l'URL de la base de données
            db_url = self.get_database_url()
            self.alembic_cfg.set_main_option("sqlalchemy.url", db_url)

            # Générer la migration initiale
            command.revision(self.alembic_cfg, message=message, autogenerate=True)

            logger.info("✅ Migration initiale créée avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de la création de la migration initiale: {e}")
            return False

    def upgrade(self, revision: str = "head") -> bool:
        """Applique les migrations"""
        try:
            logger.info(f"🔄 Application des migrations jusqu'à {revision}...")

            # Mettre à jour l'URL de la base de données
            db_url = self.get_database_url()
            self.alembic_cfg.set_main_option("sqlalchemy.url", db_url)

            command.upgrade(self.alembic_cfg, revision)

            logger.info("✅ Migrations appliquées avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'application des migrations: {e}")
            return False

    def downgrade(self, revision: str) -> bool:
        """Annule les migrations"""
        try:
            logger.info(f"🔄 Annulation des migrations jusqu'à {revision}...")

            # Mettre à jour l'URL de la base de données
            db_url = self.get_database_url()
            self.alembic_cfg.set_main_option("sqlalchemy.url", db_url)

            command.downgrade(self.alembic_cfg, revision)

            logger.info("✅ Migrations annulées avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'annulation des migrations: {e}")
            return False

    def current(self) -> Optional[str]:
        """Affiche la révision actuelle"""
        try:
            logger.info("📋 Vérification de la révision actuelle...")

            # Mettre à jour l'URL de la base de données
            db_url = self.get_database_url()
            engine = create_engine(db_url)

            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()

                if current_rev:
                    logger.info(f"📌 Révision actuelle: {current_rev}")
                else:
                    logger.info("📌 Aucune révision appliquée")

                return current_rev

        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification de la révision: {e}")
            return None

    def history(self) -> List[str]:
        """Affiche l'historique des migrations"""
        try:
            logger.info("📚 Récupération de l'historique des migrations...")

            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            revisions = []

            for revision in script_dir.walk_revisions():
                revisions.append(f"{revision.revision[:8]} - {revision.doc}")

            return revisions

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de l'historique: {e}")
            return []

    def status(self) -> dict:
        """Affiche le statut des migrations"""
        try:
            logger.info("📊 Vérification du statut des migrations...")

            db_url = self.get_database_url()
            engine = create_engine(db_url)

            status_info = {
                "database_url": db_url[:10] + "***",
                "current_revision": None,
                "head_revision": None,
                "pending_migrations": 0,
                "database_exists": False,
            }

            # Vérifier si la base de données existe
            try:
                with engine.connect() as connection:
                    status_info["database_exists"] = True

                    # Révision actuelle
                    context = MigrationContext.configure(connection)
                    current_rev = context.get_current_revision()
                    status_info["current_revision"] = current_rev

            except Exception:
                status_info["database_exists"] = False

            # Révision head
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head_rev = script_dir.get_current_head()
            status_info["head_revision"] = head_rev

            # Migrations en attente
            if status_info["current_revision"] and status_info["head_revision"]:
                if status_info["current_revision"] != status_info["head_revision"]:
                    # Compter les migrations en attente (simplification)
                    status_info["pending_migrations"] = 1
            elif not status_info["current_revision"] and status_info["head_revision"]:
                status_info["pending_migrations"] = 1

            return status_info

        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification du statut: {e}")
            return {"error": str(e)}

    def init_database(self) -> bool:
        """Initialise la base de données si elle n'existe pas"""
        try:
            logger.info("🗃️  Initialisation de la base de données...")

            db_url = self.get_database_url()
            engine = create_engine(db_url)

            # Créer les tables si nécessaire
            Base.metadata.create_all(engine)

            logger.info("✅ Base de données initialisée")
            return True

        except Exception as e:
            logger.error(
                f"❌ Erreur lors de l'initialisation de la base de données: {e}"
            )
            return False

    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Crée une sauvegarde de la base de données (SQLite uniquement)"""
        try:
            db_url = self.get_database_url()

            if not db_url.startswith("sqlite:"):
                logger.warning("⚠️  Sauvegarde uniquement supportée pour SQLite")
                return False

            # Extraire le chemin du fichier SQLite
            db_file = db_url.replace("sqlite:///", "")

            if not os.path.exists(db_file):
                logger.warning(f"⚠️  Base de données non trouvée: {db_file}")
                return False

            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{db_file}.backup_{timestamp}"

            logger.info(f"💾 Création de la sauvegarde: {backup_path}")

            import shutil

            shutil.copy2(db_file, backup_path)

            logger.info("✅ Sauvegarde créée avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {e}")
            return False

    def generate_migration(self, message: str) -> bool:
        """Génère une nouvelle migration"""
        try:
            logger.info(f"📝 Génération de la migration: {message}")

            # Mettre à jour l'URL de la base de données
            db_url = self.get_database_url()
            self.alembic_cfg.set_main_option("sqlalchemy.url", db_url)

            command.revision(self.alembic_cfg, message=message, autogenerate=True)

            logger.info("✅ Migration générée avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération de la migration: {e}")
            return False


def print_status(status_info: dict):
    """Affiche le statut des migrations de façon formatée"""
    print("\n📊 STATUT DES MIGRATIONS")
    print("=" * 50)

    if "error" in status_info:
        print(f"❌ Erreur: {status_info['error']}")
        return

    print(f"🔗 Base de données: {status_info['database_url']}")
    print(f"🗃️  Existe: {'✅ Oui' if status_info['database_exists'] else '❌ Non'}")
    print(f"📌 Révision actuelle: {status_info['current_revision'] or 'Aucune'}")
    print(f"🎯 Révision head: {status_info['head_revision'] or 'Aucune'}")
    print(f"⏳ Migrations en attente: {status_info['pending_migrations']}")

    if status_info["pending_migrations"] > 0:
        print("\n⚠️  Des migrations sont en attente d'application!")
        print("💡 Utilisez 'python migrate.py upgrade' pour les appliquer")
    else:
        print("\n✅ Base de données à jour!")


def main():
    parser = argparse.ArgumentParser(
        description="Gestionnaire de migrations pour l'application FastHTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
    migrate init                          # Initialise la base de données
    migrate generate "Add user table"     # Génère une nouvelle migration
    migrate upgrade                       # Applique toutes les migrations
    migrate downgrade -1                  # Annule la dernière migration
    migrate status                        # Affiche le statut
    migrate backup                        # Crée une sauvegarde
    migrate history                       # Affiche l'historique
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "init",
            "generate",
            "upgrade",
            "downgrade",
            "status",
            "current",
            "history",
            "backup",
        ],
        help="Commande à exécuter",
    )

    parser.add_argument(
        "message_or_revision",
        nargs="?",
        help="Message pour generate, révision pour downgrade",
    )

    parser.add_argument(
        "--config",
        default="alembic.ini",
        help="Chemin vers le fichier de configuration Alembic (défaut: alembic.ini)",
    )

    parser.add_argument("--backup-path", help="Chemin pour la sauvegarde (optionnel)")

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Affichage détaillé"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    try:
        manager = MigrationManager(args.config)

        if args.command == "init":
            print("🚀 Initialisation de la base de données...")
            success = manager.init_database()
            if success:
                print("✅ Base de données initialisée avec succès!")
            else:
                print("❌ Échec de l'initialisation")
                sys.exit(1)

        elif args.command == "generate":
            if not args.message_or_revision:
                print("❌ Message requis pour la génération de migration")
                sys.exit(1)

            success = manager.generate_migration(args.message_or_revision)
            if not success:
                sys.exit(1)

        elif args.command == "upgrade":
            revision = args.message_or_revision or "head"
            success = manager.upgrade(revision)
            if not success:
                sys.exit(1)

        elif args.command == "downgrade":
            if not args.message_or_revision:
                print("❌ Révision requise pour le downgrade")
                sys.exit(1)

            success = manager.downgrade(args.message_or_revision)
            if not success:
                sys.exit(1)

        elif args.command == "status":
            status_info = manager.status()
            print_status(status_info)

        elif args.command == "current":
            current_rev = manager.current()
            if current_rev:
                print(f"📌 Révision actuelle: {current_rev}")
            else:
                print("📌 Aucune révision appliquée")

        elif args.command == "history":
            revisions = manager.history()
            if revisions:
                print("\n📚 HISTORIQUE DES MIGRATIONS")
                print("=" * 50)
                for rev in reversed(revisions):
                    print(f"  {rev}")
            else:
                print("📚 Aucune migration trouvée")

        elif args.command == "backup":
            success = manager.backup_database(args.backup_path)
            if not success:
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Opération interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

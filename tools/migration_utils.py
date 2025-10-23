#!/usr/bin/env python3
"""
Migration utilities for database management
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from sqlalchemy import create_engine, inspect

    from data import Base

    from . import cfg, logger
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class DatabaseInspector:
    """Database inspection utilities"""

    def __init__(self, database_url: str = cfg.get("database_url", "url")):
        self.database_url = database_url
        self.engine = create_engine(database_url)

    def get_table_info(self) -> Dict:
        """Get information about all tables"""
        try:
            inspector = inspect(self.engine)
            tables_info = {}

            for table_name in inspector.get_table_names():
                tables_info[table_name] = {
                    "columns": inspector.get_columns(table_name),
                    "indexes": inspector.get_indexes(table_name),
                    "foreign_keys": inspector.get_foreign_keys(table_name),
                    "primary_key": inspector.get_pk_constraint(table_name),
                    "unique_constraints": inspector.get_unique_constraints(table_name),
                }

            return tables_info
        except Exception as e:
            logger.error(f"❌ Error inspecting tables: {e}")
            return {}

    def export_schema(self, output_file: str):
        """Export database schema"""
        try:
            tables_info = self.get_table_info()

            schema_data = {
                "export_date": datetime.now().isoformat(),
                "database_url": self.database_url[:30] + "***",
                "tables": tables_info,
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(schema_data, f, indent=2, default=str)

            logger.info(f"✅ Schema exported to {output_file}")
        except Exception as e:
            logger.error(f"❌ Error exporting schema: {e}")


class BackupManager:
    """Backup management utilities"""

    def __init__(self, database_url: str = cfg.get("database_url", "url")):
        self.database_url = database_url
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """Create database backup"""
        try:
            if not self.database_url.startswith("sqlite:"):
                logger.error("❌ Backup only supported for SQLite")
                return None

            db_file = self.database_url.replace("sqlite:///", "")

            if not os.path.exists(db_file):
                logger.error(f"❌ Database file not found: {db_file}")
                return None

            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}.db"

            backup_path = self.backup_dir / backup_name
            shutil.copy2(db_file, backup_path)

            logger.info(f"✅ Backup created: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None

    def restore_backup(
        self, backup_file: str, target_file: Optional[str] = None
    ) -> bool:
        """Restore a backup"""
        try:
            if not self.database_url.startswith("sqlite:"):
                logger.error("❌ Restore only supported for SQLite")
                return False

            db_file = self.database_url.replace("sqlite:///", "")

            if not os.path.exists(backup_file):
                logger.error(f"❌ Backup file not found: {backup_file}")
                return False

            target_file = target_file or db_file
            shutil.copy2(backup_file, target_file)

            logger.info(f"✅ Database restored from {backup_file} to {target_file}")
            return True

        except Exception as e:
            logger.error(f"❌ Error restoring backup: {e}")
            return False

    def list_backups(self) -> list:
        """List available backups"""
        try:
            backups = list(self.backup_dir.glob("*.db"))
            list_backups = [str(backup) for backup in backups]
            for backup in list_backups:
                logger.info(f"✅ Backup found: {backup}")
        except Exception as e:
            logger.error(f"❌ Error listing backups: {e}")
            return []

    def delete_backup(self, backup_file: str) -> bool:
        try:
            os.remove(backup_file)
            logger.info(f"✅ Backup deleted: {backup_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting backup: {e}")
            return False

    def delete_all_backups(self) -> bool:
        try:
            for backup_file in self.backup_dir.glob("*.db"):
                os.remove(backup_file)
            logger.info("✅ All backups deleted")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting backups: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Database migration utilities")
    parser.add_argument(
        "action",
        choices=[
            "inspect",
            "export",
            "backup",
            "restore",
            "list-backup",
            "delete-backup",
            "delete-all-backup",
        ],
        help="Action to perform",
    )
    parser.add_argument(
        "--url", help="Database URL (default: cfg.get('database_url', 'url'))"
    )
    parser.add_argument("--output", help="Output file for schema export")
    parser.add_argument("--backup", help="Backup file name (for create/restore)")

    args = parser.parse_args()

    # Fallback sur DATABASE.URL si --url n’est pas fourni

    db_url = args.url or cfg.get("database_url", "url")
    if args.action == "inspect":
        inspector = DatabaseInspector(db_url)
        tables = inspector.get_table_info()
        print(json.dumps(tables, indent=2, default=str))

    elif args.action == "export":
        if not args.output:
            print("❌ --output is required for export")
            sys.exit(1)
        inspector = DatabaseInspector(db_url)
        inspector.export_schema(args.output)

    elif args.action == "backup":
        backup_mgr = BackupManager(db_url)
        backup_mgr.create_backup(args.backup)

    elif args.action == "restore":
        if not args.backup:
            print("❌ --backup is required for restore")
            sys.exit(1)
        backup_mgr = BackupManager(db_url)
        backup_mgr.restore_backup(args.backup)

    elif args.action == "list-backup":
        backup_mgr = BackupManager(db_url)
        backup_mgr.list_backups()

    elif args.action == "delete-backup":
        if not args.backup:
            print("❌ --backup is required for delete")
            sys.exit(1)
        backup_mgr = BackupManager(db_url)
        backup_mgr.delete_backup(args.backup)

    elif args.action == "delete-all-backup":
        backup_mgr = BackupManager(db_url)
        backup_mgr.delete_all_backups()


if __name__ == "__main__":
    main()

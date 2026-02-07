# plugins - Plugin Development Guide

## Overview

The `plugins` directory contains dynamically loadable plugins. Each plugin is a self-contained module with its own models, schemas, API routes, and business logic. Plugins can be installed, enabled, disabled, and uninstalled at runtime.

## Module Structure

```
plugins/
├── __init__.py              # Auto-generated plugin initialization
└── LibraryHub/              # Example plugin: Library Management
    ├── __init__.py          # PLUGIN_INFO and router export
    ├── run.py               # Plugin entry point
    ├── api/                 # API controllers
    │   └── author.py
    ├── core/                # Plugin core
    │   └── database.py      # Plugin-specific database
    ├── models/              # SQLAlchemy models
    │   ├── author.py
    │   ├── book.py
    │   ├── category.py
    │   ├── loan.py
    │   ├── logs.py
    │   ├── member.py
    │   └── penalty.py
    ├── schemas/             # Pydantic schemas
    │   ├── author.py
    │   ├── book.py
    │   ├── category.py
    │   ├── loan.py
    │   ├── log.py
    │   ├── member.py
    │   └── penalty.py
    └── service/             # Business logic
        └── authors.py
```

## Plugin Anatomy

### Required Files

Every plugin must have these files:

1. `__init__.py` - Plugin metadata and router export
2. `run.py` - Plugin class with lifecycle hooks

### Plugin Metadata (`__init__.py`)

```python
# PLUGIN_INFO - Required metadata dictionary
PLUGIN_INFO = {
    "id": "my_plugin",           # Unique plugin ID (required)
    "name": "My Plugin",         # Display name (required)
    "version": "1.0.0",          # Semantic version (required)
    "description": "A sample plugin",  # Description (optional)
    "author": "Developer Name",  # Author (optional)
    "dependencies": [],          # Other plugin IDs required (optional)
    "min_core_version": "1.0.0", # Minimum xcore version (optional)
    "tags": ["sample", "demo"]   # Tags for categorization (optional)
}

# Export router for automatic registration
from .api.routes import router
__all__ = ["router", "PLUGIN_INFO"]
```

### Plugin Class (`run.py`)

```python
from manager.plManager.loader import Plugin

class Plugin(Plugin):
    """Plugin lifecycle management"""

    def __init__(self):
        self.name = "my_plugin"
        self.enabled = False

    def on_install(self):
        """Called when plugin is installed"""
        # Create database tables
        # Initialize default data
        pass

    def on_enable(self):
        """Called when plugin is enabled"""
        # Register event listeners
        # Start background tasks
        pass

    def on_disable(self):
        """Called when plugin is disabled"""
        # Unregister event listeners
        # Stop background tasks
        pass

    def on_uninstall(self):
        """Called when plugin is uninstalled"""
        # Clean up database tables
        # Remove stored data
        pass

    def on_update(self, from_version: str):
        """Called when plugin is updated"""
        # Run migration scripts
        pass
```

## Creating a Plugin

### Step 1: Create Plugin Directory

```bash
mkdir -p plugins/my_plugin/{api,models,schemas,service}
touch plugins/my_plugin/__init__.py
```

### Step 2: Define Plugin Metadata

```python
# plugins/my_plugin/__init__.py
PLUGIN_INFO = {
    "id": "my_plugin",
    "name": "My Custom Plugin",
    "version": "1.0.0",
    "description": "Demonstrates plugin development",
    "author": "Your Name",
    "dependencies": [],
    "tags": ["demo", "tutorial"]
}

from fastapi import APIRouter
from .api import routes

router = routes.router
__all__ = ["router", "PLUGIN_INFO"]
```

### Step 3: Create Models

```python
# plugins/my_plugin/models/item.py
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from database.db import Base

class Item(Base):
    __tablename__ = "my_plugin_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### Step 4: Create Schemas

```python
# plugins/my_plugin/schemas/item.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class ItemUpdate(ItemBase):
    name: Optional[str] = None

class ItemRead(ItemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
```

### Step 5: Create API Routes

```python
# plugins/my_plugin/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.db import get_db
from ..models.item import Item
from ..schemas.item import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/my_plugin/items", tags=["my_plugin"])

@router.get("/", response_model=list[ItemRead])
async def list_items(db: Session = Depends(get_db)):
    """List all items"""
    return db.query(Item).all()

@router.post("/", response_model=ItemRead)
async def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Create a new item"""
    db_item = Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get item by ID"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.put("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    db: Session = Depends(get_db)
):
    """Update an item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in item_data.dict(exclude_unset=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}")
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Delete an item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}
```

### Step 6: Create Plugin Class

```python
# plugins/my_plugin/run.py
from manager.plManager.loader import Plugin
from database.db import engine, Base
from .models.item import Item

class Plugin(Plugin):
    """My Plugin lifecycle management"""

    def __init__(self):
        self.name = "my_plugin"
        self.enabled = False

    def on_install(self):
        """Create database tables"""
        Item.__table__.create(bind=engine, checkfirst=True)

    def on_enable(self):
        """Plugin enabled"""
        print(f"Plugin {self.name} enabled")

    def on_disable(self):
        """Plugin disabled"""
        print(f"Plugin {self.name} disabled")

    def on_uninstall(self):
        """Drop database tables"""
        Item.__table__.drop(bind=engine)
```

## Advanced Features

### Plugin Database

Plugins can use their own database:

```python
# plugins/my_plugin/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./my_plugin.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Plugin Dependencies

Declare dependencies in PLUGIN_INFO:

```python
PLUGIN_INFO = {
    "id": "advanced_plugin",
    "name": "Advanced Plugin",
    "version": "1.0.0",
    "dependencies": ["base_plugin"],  # Must be installed first
}
```

### Hook Integration

```python
# plugins/my_plugin/run.py
from hooks import hook_manager

class Plugin(Plugin):
    def on_enable(self):
        # Register hooks
        hook_manager.register("user.created", self.on_user_created)
        hook_manager.register("app.startup", self.on_startup)

    def on_disable(self):
        # Unregister hooks
        hook_manager.unregister("user.created", self.on_user_created)

    def on_user_created(self, user):
        """Handle user creation event"""
        print(f"New user created: {user.username}")

    def on_startup(self):
        """Handle application startup"""
        print("Application started")
```

### Custom CLI Commands

```python
# plugins/my_plugin/cli.py
import click

@click.group()
def cli():
    """My Plugin CLI"""
    pass

@cli.command()
def init():
    """Initialize plugin data"""
    print("Initializing my_plugin...")

@cli.command()
@click.argument("name")
def greet(name):
    """Greet someone"""
    print(f"Hello, {name}!")
```

### Scheduled Tasks

```python
# plugins/my_plugin/run.py
from manager.task.taskmanager import TaskManager

class Plugin(Plugin):
    def on_enable(self):
        # Add scheduled task
        TaskManager.add_task(
            func=self.cleanup_task,
            trigger="interval",
            id=f"{self.name}_cleanup",
            hours=24
        )

    def on_disable(self):
        # Remove scheduled task
        TaskManager.remove_task(f"{self.name}_cleanup")

    def cleanup_task(self):
        """Run daily cleanup"""
        print("Running cleanup task...")
```

### Plugin Configuration

```python
# plugins/my_plugin/config.py
from configurations.base import BaseConfig

class MyPluginConfig(BaseConfig):
    """Configuration for my plugin"""

    api_key: str = ""
    endpoint_url: str = "https://api.example.com"
    timeout: int = 30
    max_items: int = 100

config = MyPluginConfig()
```

### Plugin Frontend Components

```python
# plugins/my_plugin/components.py
from frontend.microui.components import Card, Button

def render_item_card(item):
    """Render item as a card component"""
    card = Card(
        title=item.name,
        content=item.description,
        footer=Button(label="View", variant="primary").render()
    )
    return card.render()
```

## Plugin Lifecycle

```
Install    → on_install()    → Database setup, initial data
Enable     → on_enable()     → Register routes, hooks, tasks
           ← Running         ← Plugin is active
Disable    → on_disable()    → Unregister routes, hooks, tasks
Uninstall  → on_uninstall()  → Cleanup database, files
```

## Best Practices

### 1. Namespace Database Tables

```python
# Good
__tablename__ = "my_plugin_items"

# Bad
__tablename__ = "items"  # May conflict with other plugins
```

### 2. Use Plugin-Specific Logger

```python
import logging
logger = logging.getLogger(f"plugins.{PLUGIN_INFO['id']}")

logger.info("Plugin initialized")
logger.error("Something went wrong")
```

### 3. Handle Dependencies Gracefully

```python
try:
    from other_plugin.models import RelatedModel
except ImportError:
    RelatedModel = None
    logger.warning("other_plugin not available")
```

### 4. Version Your API

```python
router = APIRouter(
    prefix="/v1/my_plugin",  # Version your endpoints
    tags=["my_plugin"]
)
```

### 5. Document Your Plugin

```python
PLUGIN_INFO = {
    "id": "my_plugin",
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "Brief description",
    "author": "Your Name",
    "license": "MIT",
    "homepage": "https://github.com/user/my_plugin",
    "documentation": "https://docs.example.com/my_plugin"
}
```

## Plugin Installation

### Via Manager API

```python
from manager import Manager

# Install from path
Manager.install("/path/to/my_plugin")

# Enable
Manager.enable("my_plugin")

# Disable
Manager.disable("my_plugin")

# Uninstall
Manager.uninstall("my_plugin")
```

### Via CLI

```bash
# Install plugin
python -m manager install /path/to/my_plugin

# Enable
python -m manager enable my_plugin

# Disable
python -m manager disable my_plugin

# List
python -m manager list
```

## Example: LibraryHub Plugin

The included `LibraryHub` plugin demonstrates a complete implementation:

```
plugins/LibraryHub/
├── __init__.py          # PLUGIN_INFO, router
├── run.py               # Plugin class
├── api/
│   └── author.py        # Author endpoints
├── core/
│   └── database.py      # Plugin DB setup
├── models/              # All SQLAlchemy models
├── schemas/             # All Pydantic schemas
└── service/
    └── authors.py       # Business logic
```

## Dependencies

- `manager` - Plugin management
- `database` - Database access
- `auth` - Authentication (optional)
- `frontend` - UI components (optional)

## Related Documentation

- [manager.md](manager.md) - Plugin management
- [hooks.md](hooks.md) - Hook system
- [frontend.md](frontend.md) - UI components

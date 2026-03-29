# Quick Start Guide

This guide will help you set up a basic XCore application and create your first plugin in under 10 minutes.

## Setup a Basic XCore Application

First, ensure you've followed the [Installation](installation.md) guide.

1.  **Create a Project Directory**:
    ```bash
    mkdir my-xcore-app
    cd my-xcore-app
    ```

2.  **Create a Configuration File (`xcore.yaml`)**:
    ```yaml
    app:
      name: "My XCore App"
      debug: true

    plugins:
      directory: "plugins/"
      autoload: true

    services:
      cache:
        backend: "memory"
        ttl: 300
      database:
        enabled: true
        databases:
          db:
            url: "sqlite+aiosqlite:///./xcore.db"
    ```

3.  **Initialize the Application**:
    ```python
    # app.py
    import asyncio
    from xcore import Xcore
    from fastapi import FastAPI

    xcore = Xcore(config_path="xcore.yaml")
    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        await xcore.boot(app)

    @app.on_event("shutdown")
    async def shutdown():
        await xcore.shutdown()

    @app.get("/")
    async def root():
        return {"status": "XCore is running!"}
    ```

## Create Your First Plugin

Plugins are the building blocks of XCore applications. Let's create a simple "Hello" plugin.

1.  **Create Plugin Directory Structure**:
    ```bash
    mkdir -p plugins/hello_plugin/src
    ```

2.  **Define the Plugin Manifest (`plugins/hello_plugin/plugin.yaml`)**:
    ```yaml
    name: hello_plugin
    version: "1.0.0"
    author: "Your Name"
    description: "My first plugin"
    execution_mode: trusted
    entry_point: src/main.py

    permissions:
      - resource: "*"
        actions: ["execute"]
        effect: allow
    ```

3.  **Implement the Plugin Logic (`plugins/hello_plugin/src/main.py`)**:
    ```python
    from xcore.sdk import TrustedBase, ok, error

    class Plugin(TrustedBase):
        """A simple plugin to say hello."""

        async def on_load(self) -> None:
            print("Hello Plugin Loaded!")

        async def handle(self, action: str, payload: dict) -> dict:
            if action == "greet":
                name = payload.get("name", "World")
                return ok(message=f"Hello, {name}!")

            return error(f"Action '{action}' not found.")
    ```

## Run and Test Your Plugin

1.  **Start the Server**:
    ```bash
    poetry run uvicorn app:app --port 8000
    ```

2.  **Call Your Plugin via the CLI**:
    ```bash
    PYTHONPATH=. python -m xcore.cli.main plugin list
    ```
    You should see `hello_plugin` in the list.

3.  **Test the "greet" Action**:
    ```bash
    # Call from CLI (if implemented)
    PYTHONPATH=. python -m xcore.cli.main plugin call hello_plugin greet '{"name": "Jules"}'
    ```

4.  **Expose the Plugin via FastAPI (Optional)**:
    Modify your `Plugin` class to add a router:
    ```python
    from fastapi import APIRouter

    class Plugin(TrustedBase):
        # ... on_load and handle methods

        def get_router(self) -> APIRouter:
            router = APIRouter(prefix="/hello")

            @router.get("/greet/{name}")
            async def hello_api(name: str):
                return {"message": f"Hello, {name}!"}

            return router
    ```
    Restart the server and visit `http://localhost:8000/plugins/hello_plugin/hello/greet/Jules`.

## What's Next?

- [Learn how to create advanced plugins](../guides/creating-plugins.md)
- [Understand the security and sandboxing features](../guides/security.md)
- [Work with shared services like Database and Cache](../guides/services.md)

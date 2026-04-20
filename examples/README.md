# XCore Code Examples

This directory contains standalone, runnable examples demonstrating the core features of XCore.

## 📁 Examples Structure

1.  **[01_basic_plugin](./01_basic_plugin)**: The "Hello World" of XCore. Shows how to create a Trusted plugin with simple actions.
2.  **[02_sandboxed_service](./02_sandboxed_service)**: Demonstrates the multi-layer security sandbox, resource limits, and restricted imports.
3.  **[03_fastapi_integration](./03_fastapi_integration)**: A complete web application showing how XCore integrates with FastAPI, mounts routes, and uses shared services (Cache).

---

## 🚀 How to Run

### Prerequisites
Ensure you have `xcore-framework` installed in your environment:
```bash
pip install xcore-framework
```

### Running a specific example

#### 01. Basic Plugin
```bash
cd 01_basic_plugin
xcore plugin call basic_plugin greet '{"name": "Developer"}'
```

#### 02. Sandboxed Service
```bash
cd 02_sandboxed_service
xcore plugin call sandboxed_service calculate_sqrt '{"value": 16}'
```

#### 03. FastAPI Integration
```bash
cd 03_fastapi_integration
# Start the server
python app.py
# In another terminal, test the route:
curl http://localhost:8000/plugin/weather/forecast/London
```

---

## 💡 Key Concepts Demonstrated

-   **`plugin.yaml`**: Every plugin needs a manifest.
-   **Execution Modes**: `trusted` (fast, full access) vs `sandboxed` (secure, isolated).
-   **`@action`**: Exposing methods for IPC (Inter-Plugin Communication).
-   **`@route`**: Mounting HTTP endpoints directly onto FastAPI.
-   **`get_service()`**: Accessing shared infrastructure like Caching or Databases.

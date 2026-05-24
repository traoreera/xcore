---
title: Plugin Registry
description: Understanding the global plugin index, versioning, and service scoping in Xcore.
icon: material/file-certificate
---

# Plugin Registry

The `PluginRegistry` acts as the global directory for your Xcore application. While the `PluginSupervisor` manages the runtime state (executing calls, handling restarts), the Registry focuses on metadata, dependency resolution, and service access control.

---

### Key Concepts

#### The Global Index
As plugins are loaded, they are registered in the global index. This allows any component of the system to discover which plugins are available, their current version, and who developed them.

#### Service Scoping
One of the most important roles of the Registry is enforcing service isolation. When a plugin registers a service in the container, it can specify a **Scope**:

- **`public`** (Default): The service is accessible by any other plugin in the system.
- **`private`**: The service can only be used by the plugin that registered it.
- **`protected`**: Reserved for kernel-level services. Attempting to overwrite a protected service results in a `PermissionError`.

#### Dependency Resolution (Kahn's Algorithm)
Before the framework boots, the `DependencyResolver` analyzes the `requires:` block of every `plugin.yaml`. It uses **Kahn's Algorithm** to determine the correct loading order and detects circular dependencies before any code is executed.

---

### Practical Guide

#### Introspecting the Registry
You can use the Registry to dynamically discover capabilities at runtime.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        if action == "list_extensions":
            # Search for plugins by a keyword in their description
            search_results = self.ctx.registry.search("payment")
            return ok(plugins=[p["name"] for p in search_results])
```

#### Registering Scoped Services
When your plugin provides a service to others, you can control its visibility.

```python linenums="1"
class Plugin(TrustedBase):
    async def on_load(self):
        # Register a public service
        self.ctx.registry.register_service(
            plugin_name=self.name,
            service_name="payment_gateway",
            service_obj=self.gateway_instance,
            scope="public"
        )
```

---

### API Reference

#### `PluginRegistry` Methods
| Method | Return Type | Description |
|--------|-------------|-------------|
| `get_info(name)` | `dict` | Returns metadata from the manifest (without the handler). |
| `all_plugins()` | `list[dict]` | Returns a list of metadata for all registered plugins. |
| `get_service(name, requester)` | `Any` | Returns a service only if the requester has permission. |
| `search(query)` | `list[dict]` | Case-insensitive search across name, description, and author. |
| `dependents_of(name)`| `list[str]` | Lists plugins that rely on the specified plugin. |

#### `DependencyResolver`
| Method | Description |
|--------|-------------|
| `resolve()` | Returns a flat list of plugin names in loading order. |
| `waves()` | Returns a list of waves for parallel loading. |

---

### Common Errors & Pitfalls

!!! danger "CircularDependencyError"
    Occurs when Plugin A requires Plugin B, and Plugin B requires Plugin A.
    **Fix**: Move the shared logic into a separate "base" plugin that both A and B can depend on.

!!! warning "PermissionError: Accès refusé au service privé"
    This happens if you try to use `get_service()` on a resource that another plugin has marked as `private`.
    **Fix**: Contact the plugin author or check if there is a public alternative.

!!! failure "MissingDependencyError"
    A plugin listed in a `requires:` block was not found in the `plugins/` directory.
    **Fix**: Ensure all required plugins are installed and their `name` in `plugin.yaml` matches exactly.

---

### Best Practices

!!! success "Use Descriptive Manifests"
    The Registry makes your `description` and `author` searchable. Provide clear, concise metadata to make your plugins easier to find and use.

!!! tip "Default to Public Scoping"
    Unless you are protecting sensitive internal logic, keep your services `public`. This maximizes the extensibility and modularity of the Xcore ecosystem.

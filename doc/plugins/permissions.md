---
title: Permissions & Policies
description: Understanding Xcore's fail-closed permission system and policy evaluation.
icon: material/shield-lock
---

# Permissions & Policies

Xcore implements a **fail-closed** security model. By default, a plugin has no permissions to access external resources or call other plugins. Every access must be explicitly granted in the `plugin.yaml` manifest.

---

### Prerequisites

- [x] [Plugin Anatomy](./plugin-anatomy.md)
- [x] Understanding of [Execution Modes](../kernel/execution-modes.md)

---

### Key Concepts

#### Fail-Closed Design
If a plugin does not declare a `permissions` block, it is assigned a `DENY ALL` policy. This ensures that a newly added or compromised plugin cannot access sensitive data or services without explicit authorization.

#### Policy Structure
A policy consists of three parts:
1.  **Resource**: A glob pattern identifying the target (e.g., `db.*`, `plugin:auth`, `cache.users`).
2.  **Actions**: A list of allowed verbs (e.g., `read`, `write`, `execute`, `*`).
3.  **Effect**: Either `allow` or `deny`.

#### First-Match-Wins
Policies are evaluated in the order they are defined in the manifest. The first rule that matches the resource and action determines the result. If no rules match, the access is denied.

---

### Practical Guide

#### Defining Policies
Add a `permissions` section to your `plugin.yaml`.

```yaml linenums="1" title="plugin.yaml"
permissions:
  - resource: "db.*"         # (1)
    actions: ["read", "write"]
    effect: allow

  - resource: "plugin:auth"   # (2)
    actions: ["execute"]
    effect: allow

  - resource: "os.*"         # (3)
    actions: ["*"]
    effect: deny
```

1.  Allows any database operation.
2.  Allows calling the `auth` plugin.
3.  Explicitly blocks any OS-level calls (even if granted by a later wildcard).

#### Wildcard Usage
Xcore uses standard glob patterns for resource matching:
- `*`: Matches anything (e.g., `db.*` matches `db.users` and `db.orders`).
- `?`: Matches a single character.
- `[seq]`: Matches any character in `seq`.

---

### Common Resource Strings

While the `resource` string can be arbitrary, the framework and built-in services use these conventions:

| Resource Pattern | Description |
|------------------|-------------|
| `db.<table>` | Access to a specific database table. |
| `cache.<key>` | Access to a specific cache namespace or key. |
| `plugin:<name>` | Permission to call another plugin via IPC. |
| `events:<name>` | Permission to emit or subscribe to specific events. |
| `service:<name>` | Permission to access a system service (e.g., `scheduler`). |

---

### API Reference

#### `PermissionEngine`
The engine manages the evaluation and auditing of all permissions.

| Method | Description |
|--------|-------------|
| `check(plugin, resource, action)` | Verifies permission. Raises `PermissionDenied` if unauthorized. |
| `allows(plugin, resource, action)` | Returns `True` or `False`. Used for conditional logic. |
| `audit_log(plugin, limit)` | Retrieves the recent history of permission checks. |

---

### YAML Configuration

The `security` section in `xcore.yaml` can define global defaults (rarely used, as plugins should be self-contained).

```yaml
security:
  rate_limit_default:
    calls: 100
    period_seconds: 60
```

---

### Common Errors & Pitfalls

!!! danger "PermissionDenied: Accès refusé"
    The most common error. It means the plugin tried to perform an action not listed in its manifest.
    **Fix**: Add the missing resource/action to the `permissions` block in `plugin.yaml`.

!!! warning "Policy Order"
    If you have an `allow: *` followed by a `deny: db.*`, the deny rule will **never** be reached. Always put specific rules before general ones.

!!! failure "Silent Deny"
    If you omit the `permissions` block entirely, Xcore will log a `DEBUG` message: `Aucune permission déclarée → DENY ALL`.

---

### Best Practices

!!! success "Principle of Least Privilege"
    Only grant the specific resources and actions your plugin needs. Avoid using `*` unless absolutely necessary.

!!! tip "Use Audit Logs for Debugging"
    If you're unsure why a permission is being denied, check the audit log via the CLI:
    ```bash
    xcore plugin permissions <name> --audit
    ```

---

### See Also

[Trusted Plugins](./trusted-plugins.md)
:   How to use `check()` and `allows()` inside your code.

[Middleware Pipeline](../advanced/middleware.md)
:   Understand where the `PermissionMiddleware` sits in the request flow.

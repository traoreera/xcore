---
title: Security & Sandboxing
description: Deep dive into Xcore's security architecture, including AST scanning and plugin signing.
icon: material/shield-account
---

# Security & Sandboxing

Xcore employs a multi-layered security strategy to protect the host system and ensure the integrity of the plugin ecosystem. This includes static analysis, runtime isolation, and cryptographic verification.

---

### Prerequisites

- [x] [Execution Modes](../kernel/execution-modes.md) (Trusted vs. Sandboxed) understood
- [x] [C++ Scanner Build](../installation.md#3-compile-the-c-security-scanner) completed

---

### Security Layers

#### 1. Manifest Validation
Before any plugin is loaded, Xcore validates its `plugin.yaml` against a strict schema. It ensures that required fields (name, version, entry_point) are present and that execution modes and resource limits are within acceptable bounds.

#### 2. AST Scanning (Static Analysis)
For **Sandboxed** plugins, Xcore performs a deep scan of the source code using an Abstract Syntax Tree (AST) parser.
- **Import Classification**: The scanner checks every `import` statement against a whitelist of allowed modules and a blacklist of forbidden ones (`os`, `subprocess`, `ctypes`, etc.).
- **Builtin Protection**: Access to dangerous builtins like `exec()`, `eval()`, and `__builtins__` is detected and blocked.
- **High Performance**: If compiled, a C++ implementation (`scanner_core.cpp`) is used for near-instant scanning of large plugin directories.

#### 3. Filesystem Guard (Runtime Isolation)
Inside the sandboxed subprocess, the `FilesystemGuard` monkey-patches Python's I/O primitives (`open`, `pathlib`, `os.listdir`).
- **Path Resolution**: All paths are resolved to absolute, real paths to prevent directory traversal attacks (e.g., `../../etc/passwd`).
- **Fail-Closed**: Any file access outside the declared `allowed_paths` in `plugin.yaml` raises a `PermissionError`.

#### 4. Plugin Signing (Integrity)
To prevent unauthorized modification of **Trusted** plugins, Xcore supports mandatory HMAC-based signatures.

```bash
# Generate a signature for a plugin
xcore plugin sign ./plugins/my_trusted_plugin --key MY_SECRET_KEY
```

When `strict_trusted: true` is enabled in `xcore.yaml`, Xcore will:
1.  Verify the existence of `plugin.sig`.
2.  Compute a deterministic HMAC of the manifest and all source files.
3.  Compare it against the signature file using a constant-time `hmac.compare_digest`.

---

### Practical Guide

#### Compiling the Security Scanner
For the best performance in production, ensure the C++ scanner is compiled.

```bash
cd xcore/kernel/security
python setup.py build_ext --inplace
```

#### Configuring Global Security
Adjust the framework's security stance in your main configuration file.

```yaml linenums="1" title="xcore.yaml"
security:
  strict_trusted: true    # (1)!
  scan_on_load: true      # (2)!
  secret_key: "..."       # (3)!
```

1.  Mandatory signature check for all Trusted plugins.
2.  Re-scan Sandboxed plugins on every load (even if they haven't changed).
3.  The key used for HMAC signature verification.

---

### API Reference

#### `ASTScanner`
| Method | Description |
|--------|-------------|
| `scan(plugin_dir, ...)` | Scans a directory and returns a `ScanResult` with errors and warnings. |

#### `Signature`
| Method | Description |
|--------|-------------|
| `sign_plugin(manifest, key)` | Computes the HMAC and writes the `plugin.sig` file. |
| `verify_plugin(manifest, key)`| Validates the plugin integrity. Raises `SignatureError` on failure. |

---

### Common Errors & Pitfalls

!!! danger "SignatureError: Signature invalide"
    This means the content of a signed plugin has been modified since it was signed.
    **Fix**: Re-sign the plugin after your changes using the `xcore plugin sign` command.

!!! warning "PermissionError: [sandbox] BLOCKED"
    The `FilesystemGuard` caught an unauthorized file access.
    **Fix**: Check if you need to add the path to `allowed_paths` in `plugin.yaml`.

!!! failure "Scanner Performance"
    If you have hundreds of plugins and haven't compiled the C++ scanner, the boot time may increase significantly as Xcore performs the AST scan in pure Python.

---

### Best Practices

!!! success "Rotate Secret Keys"
    Treat your `plugins.secret_key` like a production password. If it is compromised, an attacker could sign malicious Trusted plugins.

!!! tip "Use Sandboxed for External Logic"
    Always default to `sandboxed` mode for plugins developed by third parties or experimental features. Only move to `trusted` mode once the code has been fully audited.

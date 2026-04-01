## 2025-03-13 - Zip Slip Protection in Plugin Installation
**Vulnerability:** The plugin installation process was vulnerable to Zip Slip (directory traversal) because it extracted files from a ZIP archive without verifying that the resolved target paths remained within the intended destination directory.
**Learning:** Naive path concatenation using `Path` objects (`dest / member`) does not prevent traversal if the member name contains `..` components. Even if the first level is stripped, nested traversals can still occur.
**Prevention:** Always resolve the final path and check it against the destination using `target.resolve().is_relative_to(dest.resolve())`. This ensures that even with complex relative paths or symlinks, the file will not be written outside the sandbox.

## 2026-03-14 - Directory Traversal in Dotenv Injection
**Vulnerability:** The `ManifestValidator._inject_dotenv` method allowed loading `.env` files from outside the plugin directory via the `env_file` manifest parameter.
**Learning:** Even when using `Path` objects, concatenating a base directory with a user-provided relative path containing `..` can escape the intended directory if not explicitly validated after resolution.
**Prevention:** Always use `.resolve()` on the final path and verify it stays within the intended base directory using `.is_relative_to(base_dir.resolve())`.

## 2026-03-19 - Path Traversal in CLI Plugin Management
**Vulnerability:** CLI commands (`install`, `remove`, `info`, etc.) that accepted a plugin name as an argument were vulnerable to path traversal because the name was used to construct filesystem paths without validation. An attacker could use names like `../../etc/passwd` or absolute paths to target arbitrary locations.
**Learning:** CLI arguments should be treated as untrusted user input, especially when used in filesystem operations. Concatenating a base directory with an unvalidated argument can escape the intended directory.
**Prevention:** Implement strict input validation for names and identifiers using allow-lists (e.g., regex `^[a-zA-Z0-9_-]+$`) before using them in filesystem or shell operations.

## 2026-03-24 - AST Sandbox Escape via Built-ins and Sensitive Attributes
**Vulnerability:** The `ASTScanner` was only monitoring imports, allowing plugins to use dangerous built-ins (e.g., `eval`, `exec`, `getattr`) and access sensitive internal attributes (e.g., `__subclasses__`, `__globals__`) to escape the sandbox.
**Learning:** A security scanner that only checks `import` statements is insufficient for Python, as many powerful features are available as built-ins or reachable through attribute traversal from any object.
**Prevention:** Use an AST visitor to monitor `ast.Name` (for built-ins) and `ast.Attribute` (for sensitive internals) in addition to imports. Maintain a strict blocklist of forbidden names and attributes.

## 2026-03-27 - Weak Hashing for Plugin UID Generation
**Vulnerability:** The `xcore/kernel/sandbox/worker.py` used `hashlib.md5` to generate deterministic UIDs for plugins based on their directory paths. MD5 is considered cryptographically broken and often flagged by security scanners (Bandit B324).
**Learning:** Using legacy hashing algorithms like MD5, even for non-cryptographic purposes like identifier generation, can trigger security audits and is generally discouraged in favor of more robust algorithms.
**Prevention:** Always prefer SHA256 or better for any hashing operation to ensure both security and compliance with modern safety standards.

## 2026-04-02 - AST Sandbox Bypass via Attribute-based Module Re-exports
**Vulnerability:** The `ASTScanner` was vulnerable to a bypass where sandboxed plugins could access forbidden modules (e.g., `os`, `sys`) if they were re-exported as attributes of allowed modules (e.g., `pathlib.os` or `importlib.sys`).
**Learning:** In Python, many standard library modules import and expose other sensitive modules as attributes. Blocking direct `import` statements and common dunder attributes is not enough to prevent access to forbidden functionality.
**Prevention:** Enhance the AST visitor's `visit_Attribute` method to check accessed attribute names against the full set of forbidden module names, ensuring that re-exported modules are also blocked.

## 2026-04-10 - AST Sandbox Probing via `hasattr`
**Vulnerability:** The `ASTScanner` allowed the use of the `hasattr` built-in, enabling sandboxed plugins to probe for the existence of sensitive internal attributes (e.g., `__class__`, `__subclasses__`) without triggering an access error.
**Learning:** Security sandboxes that block attribute access (like `getattr` or direct attribute access) can still be "fingerprinted" or probed using `hasattr`. This allows an attacker to discover which objects might be vulnerable to escape before attempting a blocked operation.
**Prevention:** Always include `hasattr` in the list of forbidden built-ins for restricted execution environments, alongside `getattr`, `setattr`, and `delattr`.

## 2026-04-15 - AST Sandbox Escape via Reflection Built-ins
**Vulnerability:** The `ASTScanner` allowed the use of `vars()`, `dir()`, `input()`, and `help()`. `vars()` and `dir()` enable object introspection, which can be used to discover hidden attributes or internal state to bypass security checks. `input()` and `help()` can cause DoS or information leakage in restricted environments.
**Learning:** Blacklisting a few obvious built-ins like `eval` and `exec` is insufficient. Reflection and introspection tools are equally dangerous in a sandbox as they provide the roadmap for more complex escapes. Interactive built-ins can also disrupt the sandboxed process.
**Prevention:** Maintain a comprehensive and frequently updated list of forbidden built-ins. Always include any function that allows introspection (`vars`, `dir`, `getattr`, `hasattr`, etc.) or interaction (`input`, `help`).

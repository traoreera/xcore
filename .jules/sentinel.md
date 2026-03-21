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

## 2026-03-21 - AST-based Sandbox Escape Prevention
**Vulnerability:** Plugin code could bypass basic import restrictions by using dynamic built-ins like `eval()`, `exec()`, or `getattr()`, or by accessing sensitive dunder attributes like `__globals__` to escape the sandbox.
**Learning:** Checking only the `import` statements is insufficient for a robust Python sandbox. Attackers can use introspection and dynamic execution to reach forbidden modules or modify the execution environment.
**Prevention:** Implement a comprehensive AST visitor (`_SecurityVisitor`) that intercepts `ast.Name` to block dangerous built-ins and `ast.Attribute` to block access to sensitive dunder attributes (`__globals__`, `__subclasses__`, etc.) before code execution.

## 2025-03-13 - Zip Slip Protection in Plugin Installation
**Vulnerability:** The plugin installation process was vulnerable to Zip Slip (directory traversal) because it extracted files from a ZIP archive without verifying that the resolved target paths remained within the intended destination directory.
**Learning:** Naive path concatenation using `Path` objects (`dest / member`) does not prevent traversal if the member name contains `..` components. Even if the first level is stripped, nested traversals can still occur.
**Prevention:** Always resolve the final path and check it against the destination using `target.resolve().is_relative_to(dest.resolve())`. This ensures that even with complex relative paths or symlinks, the file will not be written outside the sandbox.

## 2026-03-14 - Directory Traversal in Dotenv Injection
**Vulnerability:** The `ManifestValidator._inject_dotenv` method allowed loading `.env` files from outside the plugin directory via the `env_file` manifest parameter.
**Learning:** Even when using `Path` objects, concatenating a base directory with a user-provided relative path containing `..` can escape the intended directory if not explicitly validated after resolution.
**Prevention:** Always use `.resolve()` on the final path and verify it stays within the intended base directory using `.is_relative_to(base_dir.resolve())`.

## 2025-03-20 - Sandbox Escape via Dangerous Built-ins and Dunder Attributes
**Vulnerability:** The `ASTScanner` only blocked `__import__` calls, allowing plugins to use `eval`, `exec`, `getattr`, and access dunder attributes like `__globals__` or `__subclasses__` to escape the sandbox.
**Learning:** Simple call-based scanning is insufficient if it doesn't cover the full range of dynamic execution and introspection capabilities in Python. Blocking just `__import__` can be bypassed by aliasing other built-ins (e.g., `e = eval; e(...)`) or using `getattr`.
**Prevention:** Use `visit_Name` in `ast.NodeVisitor` to block access to dangerous built-ins even when not directly called, and use `visit_Attribute` to block access to sensitive introspection dunders.

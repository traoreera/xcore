## 2025-03-13 - Zip Slip Protection in Plugin Installation
**Vulnerability:** The plugin installation process was vulnerable to Zip Slip (directory traversal) because it extracted files from a ZIP archive without verifying that the resolved target paths remained within the intended destination directory.
**Learning:** Naive path concatenation using `Path` objects (`dest / member`) does not prevent traversal if the member name contains `..` components. Even if the first level is stripped, nested traversals can still occur.
**Prevention:** Always resolve the final path and check it against the destination using `target.resolve().is_relative_to(dest.resolve())`. This ensures that even with complex relative paths or symlinks, the file will not be written outside the sandbox.

## 2026-03-14 - Directory Traversal in Dotenv Injection
**Vulnerability:** The `ManifestValidator._inject_dotenv` method allowed loading `.env` files from outside the plugin directory via the `env_file` manifest parameter.
**Learning:** Even when using `Path` objects, concatenating a base directory with a user-provided relative path containing `..` can escape the intended directory if not explicitly validated after resolution.
**Prevention:** Always use `.resolve()` on the final path and verify it stays within the intended base directory using `.is_relative_to(base_dir.resolve())`.

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

## 2026-04-15 - Sandbox Denial of Service via Interactive Input
**Vulnerability:** Sandboxed plugins could call the  built-in, causing the isolated worker process to hang indefinitely while waiting for user input on stdin. This allowed a malicious or buggy plugin to block its assigned worker and potentially consume resources without completing its task.
**Learning:** Even if a sandbox restricts filesystem and network access, interactive functions like `input()` can be used to cause process-level Denial of Service if the IPC mechanism relies on standard input/output.
**Prevention:** Always monkey-patch interactive built-ins in the restricted execution environment to raise a `PermissionError` immediately. Additionally, include these built-ins in the static AST scanner's forbidden list to catch them before execution.

## 2026-04-20 - AST Sandbox Bypass via Custom Entry Point
**Vulnerability:** The `ASTScanner` was hardcoded to only scan the `src/` directory within a plugin. However, the execution environment (the `SandboxWorker`) used the `entry_point` from the plugin's manifest to determine the source code to load. An attacker could bypass the scan by placing malicious code in an entry point outside of `src/` (e.g., at the plugin root).
**Learning:** Security validation must be synchronized with the actual execution logic. If the scanner assumes a fixed directory structure that the runtime does not enforce, a gap is created where unvalidated code can be executed.
**Prevention:** Always derive the scanning target from the same configuration used by the runtime (e.g., the `entry_point`). Additionally, implement strict path validation (using `.resolve()` and `.is_relative_to()`) to prevent the scanner itself from being used as a vector for path traversal attacks via misconfigured manifests.

## 2026-04-22 - Plugin Signature Bypass via Custom Entry Point
**Vulnerability:** The plugin signature verification (HMAC) was hardcoded to hash only the `src/` directory, ignoring the `entry_point` specified in the manifest. This allowed modifications to the actual code if it was located elsewhere (e.g., in an `app/` folder) without invalidating the signature.
**Learning:** Security mechanisms must be consistent across all layers. Fixing a vulnerability in a static scanner (AST) but leaving it in the cryptographic integrity check (HMAC) creates a gap where the system trust is based on an incomplete set of verified files.
**Prevention:** Ensure all security components (scanners, signers, loaders) use the same manifest-driven logic to identify and resolve the plugin's code root.

## 2026-04-15 - Sandbox Denial of Service via Interactive Input
**Vulnerability:** Sandboxed plugins could call the `input()` built-in, causing the isolated worker process to hang indefinitely while waiting for user input on stdin. This allowed a malicious or buggy plugin to block its assigned worker and potentially consume resources without completing its task.
**Learning:** Even if a sandbox restricts filesystem and network access, interactive functions like `input()` can be used to cause process-level Denial of Service if the IPC mechanism relies on standard input/output.
**Prevention:** Always monkey-patch interactive built-ins in the restricted execution environment to raise a `PermissionError` immediately. Additionally, include these built-ins in the static AST scanner's forbidden list to catch them before execution.

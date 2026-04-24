# XCore Security Audit Report

## 1. Executive Summary
This report summarizes the security findings and enhancements for the XCore Framework sandbox and AST validation system. The audit focused on identifying potential sandbox escapes, AST scanner bypasses, and ensuring robust isolation for sandboxed plugins.

## 2. Sandbox Architecture
XCore uses a multi-layered security approach for untrusted plugins:
- **Process Isolation**: Plugins run in a separate subprocess.
- **Resource Limits**: `RLIMIT_AS` is used to restrict memory consumption.
- **AST Scanning**: Static analysis before loading to block forbidden imports and attributes.
- **Runtime Guards**: Monkey-patching of sensitive Python built-ins and modules (`os`, `pathlib`, `builtins`, `ctypes`) to enforce policies at execution time.

## 3. Vulnerability Research & Fixes

### 3.1 Sandbox Stability & Recursion Fix
**Issue**: The `FilesystemGuard` was interfering with the framework's own internal operations (like resolving plugin paths or loading modules via `importlib`). This could lead to a `PermissionError` during legitimate plugin loading or infinite recursion in the guard.
**Fix**: Refactored the guard to use an internal `_in_guard` flag more effectively, allowing the framework to perform necessary initialization while keeping the plugin code strictly restricted.

### 3.2 Dynamic Execution (exec/eval) Hardening
**Issue**: Blocking `exec()` entirely prevented `importlib` from loading legitimate plugin modules, as it uses `exec()` on compiled code objects.
**Fix**: The `_blocked_exec` guard was updated to allow `exec()` calls where the argument is a `types.CodeType` object (legitimate module loading) but still strictly blocks `exec("string")` which is used for dynamic code injection.
**Additional Hardening**: The `compile()` builtin was strictly blocked for sandboxed plugins. This prevents a malicious plugin from manually compiling a string into a code object to bypass the `exec` string restriction.

### 3.3 Filesystem Isolation
**Issue**: Validated the effectiveness of path traversal protections.
**Result**: The `FilesystemGuard` correctly resolves paths using `Path.resolve()` and checks them against the allowed/denied lists. Attempts to use `..` to escape the plugin directory are successfully caught.

## 4. Security Validation Results

| Test Case | Method | Result |
| :--- | :--- | :--- |
| **Forbidden Module Import** | `import os` | ✅ BLOCKED |
| **Obfuscated Import** | `__import__('o'+'s')` | ✅ BLOCKED |
| **Dynamic Execution (String)** | `exec("import os")` | ✅ BLOCKED |
| **Dynamic Execution (Code Object)** | `exec(compile(...))` | ✅ BLOCKED (compile forbidden) |
| **Filesystem Traversal** | `open("../../etc/passwd")` | ✅ BLOCKED |
| **Attribute Reflection** | `getattr(obj, "__class__")` | ✅ BLOCKED (AST) |

## 5. Recommendations
1. **Continuous Fuzzing**: Implement fuzzing for the AST scanner to identify edge cases in Python's syntax that might bypass current checks.
2. **Kernel Hardening**: Consider using OS-level sandboxing (like `seccomp` or `namespaces` on Linux) in addition to the Python-level guards for defense-in-depth.
3. **Signed Plugins**: Encourage the use of 'trusted' mode with mandatory signatures for critical extensions to reduce the reliance on sandbox isolation where performance is paramount.

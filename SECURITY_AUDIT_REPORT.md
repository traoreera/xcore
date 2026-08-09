# 🛡️ Security Audit Report — XCore Framework

## 1. Executive Summary
XCore is a "plugin-first" orchestration framework designed with a strong emphasis on security and isolation. The architecture relies on a minimalist kernel and delegates functionality to plugins, which can be executed either in **Trusted** mode (full trust, direct resource access) or **Sandboxed** mode (isolated processes with strict restrictions).

The audit reveals a robust design using defense-in-depth techniques (AST scanning, monkey-patching, OS-level isolation). Common vulnerability (OWASP) protection mechanisms are well-integrated, particularly for multi-tenancy and secret management.

---

## 2. Threat Profile
The audit evaluated XCore against three primary attack vectors:
1.  **Malicious Plugin Developer (Internal/Third-Party Threat):** Attempts to escape the sandbox, steal data from other plugins or the kernel, or cause a denial of service (DoS).
2.  **External Attacker (API):** Attempts unauthorized access to plugin actions, SQL injection, or authentication bypass.
3.  **Cross-Tenant Data Leakage (Multi-tenancy):** Tenant A attempting to access Tenant B's data.

---

## 3. Detailed Component Analysis

### 3.1. Sandbox & Isolation (The System's Core)
The sandbox system uses a multi-layered approach:
-   **Layer 1: Filesystem Guard**: Monkey-patching of `open`, `os.*`, and `pathlib.Path`. It implements a *fail-closed* policy (everything not explicitly allowed is blocked).
-   **Layer 2: Dynamic Execution**: Blocking `exec()`, `eval()`, `compile()`, and `input()` to prevent on-the-fly execution of arbitrary code.
-   **Layer 3: Import Blocking**: Prohibits importing sensitive modules (`os`, `sys`, `subprocess`, `ctypes`, etc.) via an AST scan (C++ or Python) and runtime guards.
-   **Layer 4: Resource Restrictions**: Leverages Linux's `resource` module to restrict memory (RLIMIT_AS) and CPU time.
-   **Disk Isolation**: A `DiskWatcher` monitors the plugin's `data/` directory size in real-time.

**Strengths:** Using a C++ extension for the AST scan provides high performance and resilience against simple obfuscation-based bypasses.
**Residual Risk:** On Windows systems, resource limits (memory/CPU) cannot be enforced by the kernel.

### 3.2. Plugin Integrity (Signatures)
XCore implements an HMAC-SHA256 signature system to guarantee the integrity of **Trusted** plugins.
-   **Dynamic Verification**: The hash covers the manifest and all source files.
-   **Strict Mode**: The `strict_trusted: true` parameter prevents loading any unsigned or unvalidated code.
-   **Anti-Timing Attacks**: Employs `hmac.compare_digest` for signature and API key verification.

### 3.3. Multi-tenancy & Data Isolation
Isolation is managed via asynchronous `ContextVar` instances, ensuring that requests cannot "leak" into another request's context.
-   **Database**: Uses PostgreSQL's `search_path` (schema-based isolation). A strict regex validates the `tenant_id` to prevent SQL injection during `SET search_path`.
-   **Cache & Scheduler**: Automatic and transparent prefixing of keys and IDs using the `tenant_id`.

### 3.4. API Security & RBAC
-   **IPC Authentication**: Inter-plugin and supervisor calls are protected by an API key hashed using PBKDF2 (100,000 iterations by default).
-   **RBAC System**: Extensible FastAPI dependencies (`require_role` and `require_permission`) utilizing a third-party authentication plugin.

---

## 4. OWASP Top 10 Compliance

| Category | State | XCore Implementation |
| :--- | :--- | :--- |
| **A01:2021-Broken Access Control** | ✅ Robust | Integrated RBAC, strict multi-tenant isolation, sandboxing. |
| **A02:2021-Cryptographic Failures** | ✅ Robust | PBKDF2 for keys, HMAC-SHA256 for signatures, secure hash storage. |
| **A03:2021-Injection** | ✅ Robust | SQLAlchemy `text()` used throughout, regex validation of tenant IDs. |
| **A04:2021-Insecure Design** | ✅ Robust | Default fail-closed architecture. |
| **A05:2021-Security Misconfig** | ⚠️ Caution | `CORSMiddleware` configured but requires manual activation during boot. |
| **A06:2021-Vulnerable Components** | ✅ Managed | GitHub `security.yml` workflow with dependency scanning. |
| **A07:2021-Ident & Auth Failures** | ✅ Robust | Interchangeable auth backend, timing attack protection. |
| **A08:2021-Software & Data Integrity** | ✅ Robust | Mandatory signing for Trusted plugins in strict mode. |
| **A10:2021-Server-Side Request Forgery** | ✅ Managed | Sandbox blocks network modules (`httpx`, `requests`) by default. |

---

## 5. Environment & Deployment Analysis
-   **Secret Management**: XCore validates at startup that secret keys are not set to defaults (`change-me-in-production`) if `env: production` is set.
-   **Observability**: Structured logs (JSON support available) allowing precise auditing of sandbox-blocked actions.
-   **DevOps**: Secure Dockerfile using an up-to-date base image and a non-root user (`vscode`).

---

## 6. Recommendations and Key Considerations

1.  **CORS**: Although present in the configuration, ensure you explicitly inject `CORSMiddleware` into your FastAPI application if utilizing it as a public API.
2.  **Windows**: For maximum production security, use a Linux environment to benefit from OS-level resource limits (cgroups/rlimits).
3.  **Strict Mode**: In production, always enable `strict_trusted: true` to prevent loading unsigned Trusted code.
4.  **C++ Extension**: Compile the `scanner_core.cpp` extension for optimal AST scanner performance and enhanced security.

---
**Report generated by Jules (AI Security Audit Agent)**

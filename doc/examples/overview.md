---
title: Examples Overview
description: High-scale implementation patterns using the full power of Xcore.
icon: material/lightbulb-on
---

# Examples Overview

These examples demonstrate how to build production-grade systems by combining Xcore's core subsystems. They are designed to be "no-restriction" showcases, using everything from multi-tenant isolation to distributed task execution.

---

### Implementation Patterns

#### [1. Advanced User Management](./auth-example.md)
A complete registration system with strict validation and automated tasks.
- **Features**: **SQLAlchemy Models**, **Pydantic Validation**, and **Asynchronous Events**.
- **Key Subsystems**: DB, Cache, Events, XWorker, and Scheduler.

#### [2. Distributed Transformation Engine](./sandbox-example.md)
A high-performance Sandboxed plugin for processing large datasets securely.
- **Features**: **Resource Enforcement** (CPU/RAM), **Filesystem Guard**, and **Batch IPC**.
- **Key Subsystems**: Sandbox, IPC, and Resource Limits.

#### [3. Advanced Multi-Tenant Analytics](./tenancy-example.md)
A SaaS-ready data hub that transparently isolates data per customer.
- **Features**: **Tenant Schema Switching**, **Context Propagation**, and **Isolated Scheduling**.
- **Key Subsystems**: Tenancy, DB, Events, and Scheduler.

#### [4. Advanced Scheduled Data Syncer](./scheduler-example.md)
A resilient background service for coordinating 3rd-party API integrations.
- **Features**: **Distributed Locking**, **Gateway IPC Pattern**, and **Batch Worker Offloading**.
- **Key Subsystems**: Scheduler, XWorker, Cache, and Registry.

---

### Technical Prerequisites

To run these examples without modification, ensure your `xcore.yaml` has the following services enabled:
- **PostgreSQL**: Required for tenant-aware schema isolation.
- **Redis**: Required for the `XWorker` (Celery) and persistent `Scheduler`.
- **C++ Security Scanner**: Recommended for the high-performance Sandbox example.

---

### How to use these examples

1.  **Initialize**: Run `xcore plugin init <name>` to get the boilerplate.
2.  **Paste & Adapt**: Copy the logic from the examples and adapt the `permissions` to your specific security needs.
3.  **Validate**: Use the provided `pytest` snippets to verify that inter-plugin events and background tasks are working as expected.

!!! success "Best Practice: Modularization"
    Notice how these examples separate **Persistence** (Models), **Validation** (Schemas), and **Orchestration** (Plugin logic). We recommend following this structure for all production-grade plugins.

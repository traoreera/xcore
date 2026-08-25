# Welcome to xcorecli

`xcorecli` is the official command-line companion for the **xcore ecosystem**. It provides a unified interface for project management, service monitoring, plugin lifecycles, and worker orchestration.

!!! tip "Beautiful Terminal Output"
    `xcorecli` leverages the `rich` library to deliver stunning terminal interfaces, featuring interactive tables, progress bars, and real-time dashboards.

## Key Features

- **Project Initialization**: Seamlessly scaffold new projects and manage `integration.yaml`.
- **Plugin Lifecycle**: Full control over installing, signing, and updating plugins.
- **Real-time Monitoring**: Integrated dashboard for service health and resource usage.
- **Worker Orchestration**: Manage Celery/XWorker processes with ease.
- **Security & Sandboxing**: Resource isolation and AST-based whitelisting for plugins.
- **Database Migrations**: Streamlined Alembic integration for schema management.

## Quick Start Overview

```bash title="Quick Install"
git clone https://github.com/xcore-team/xcoreCli.git
cd xcorecli
make install
```

!!! info "Architecture"
    The CLI is designed to be highly modular. Each command group (e.g., `plugin`, `worker`, `manager`) is a self-contained module, ensuring extensibility and maintainability.

## Next Steps

- [Installation Guide](getting-started/install.md)
- [Authentication Setup](getting-started/auth.md)
- [Core Commands Reference](reference.md)

!!! info "Production deployment"
    Deploying plugin bundles to remote servers is no longer part of
    `xcorecli` — it's fully handled by the standalone
    [`xcore-agent`](https://github.com/traoreera/xcore-agent) deployment
    agent (Hub artifact fetch, signature verification, install/rollback,
    systemd/Docker/Kubernetes supervisors, CI/CD watch loop).

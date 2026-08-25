# Service Extensions

The marketplace also hosts **service extensions** (`xservices`) — a
separate catalog from plugins, for reusable service-shaped dependencies a
plugin might need (databases, caches, message queues...). The `service`
command group mirrors `plugin` one-for-one, just pointed at that other
catalog.

!!! warning "Not `xcli services`"
    `xcli service` (singular, this page) is the marketplace catalog.
    `xcli services` and `xcli manager services` (plural) show your
    **local** xcore runtime's own service status — an unrelated command
    that happens to share a similar name. If a command errors with
    something about your local `ServiceContainer`, you probably typed the
    plural by mistake.

## Discovery

Read-only, public, no credentials required — same shape as
[Plugin Marketplace](../plugin/marketplace.md):

```bash
xcli service marketplace browse
xcli service marketplace browse --sort installs --limit 50
xcli service marketplace search "cache"
xcli service marketplace info name-of-service
```

`--sort` accepts `newest` (default), `installs`, or `rating` — note
`installs`, not `downloads`; the service catalog counts installs, not
downloads.

## Installing

Same two credentials as plugins — see [Authentication](../getting-started/auth.md)
(`xcli login` covers both catalogs at once; a project-scoped key is
per-catalog, so make sure the project you created it for has
`kind=service`).

```bash title="Install"
xcli service install name-of-service
xcli service install name-of-service@1.2.3
```

Installed extensions land in the directory configured under
`marketplace_services.directory` in `integration.yaml` (defaults to
`./services`) — deliberately a separate key from `plugins.directory` and
from `services.databases.*` (xcore's own internal service container
config), which already both use `services`/`plugins` for something else.

```bash
xcli service versions name-of-service
```

## Management Commands

Identical shape to `plugin`:

```bash
xcli service info name-of-service      # manifest, permissions, signature status
xcli service health                    # signature + AST + manifest check, all installed
xcli service remove name-of-service    # uninstall
```

!!! info "Smaller surface than `plugin`"
    There's no `service local`/`service runtime`/`service security`/
    `service update` today — service extensions don't have the same
    local-dev-scaffolding or hot-reload workflow plugins do. Everything
    that exists lives directly under `xcli service`.

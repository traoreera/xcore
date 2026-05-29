---
title: Plugin Marketplace
description: Discover, search, and rate plugins on the official Xcore marketplace.
icon: material/store
---

# Plugin Marketplace

Discover and explore new capabilities for your `xcore` project via the official marketplace.

## Discovery Commands

### Browse All

List everything available on the marketplace:

```bash
xcli plugin marketplace browse

# Available Plugins (42 total)
# ──────────────────────────────────────────────────────
#  Name               Author         Version   Stars
#  auth-jwt           xcore-team     3.1.0     ★★★★★
#  billing-stripe     payco          2.0.1     ★★★★☆
#  monitoring-prom    observo        1.4.2     ★★★★☆
#  email-ses          aws-plugins    1.2.0     ★★★☆☆
#  ...
```

### Search

Find plugins by keywords, tags, or categories:

```bash title="Keyword search"
xcli plugin marketplace search "monitoring"

# Results for "monitoring":
#   monitoring-prom  — Prometheus metrics exporter        v1.4.2
#   apm-elastic      — Elastic APM integration            v1.1.0
#   sentry-plugin    — Sentry error reporting             v2.3.1
```

### Trending

See what's popular in the community:

```bash
xcli plugin marketplace trending

# Trending this week:
#  1. auth-jwt          (+124 installs)
#  2. billing-stripe    (+89 installs)
#  3. monitoring-prom   (+67 installs)
```

## Viewing Plugin Details

Get in-depth information about a specific marketplace plugin before installing it:

```bash title="Plugin details"
xcli plugin marketplace info auth-jwt

# auth-jwt v3.1.0
# Author:      xcore-team
# License:     MIT
# Description: JWT authentication backend with RBAC support
# ─────────────────────────────────────────────────────
# Permissions requested:
#   cache.*   read, write
# Resources:
#   timeout:  5s
#   rate:     500/60s
# ─────────────────────────────────────────────────────
# Install: xcli plugin install auth-jwt
```

## Community Feedback

### Rating Plugins

Share your experience by rating a plugin (1 to 5 stars):

```bash
xcli plugin marketplace rate auth-jwt --score 5 --comment "Excellent JWT integration"
# Rating submitted. Thank you!
```

!!! info "API Keys"
    Interacting with the marketplace requires an API key. Configure it:
    ```bash
    xcli config set marketplace.api_key "xdk_your-token"
    ```
    Or use the environment variable `XCORE_MARKETPLACE_API_KEY`.

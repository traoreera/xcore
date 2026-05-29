---
title: Installing Plugins
description: Install plugins from the marketplace, Git repositories, or local zip archives.
icon: material/package-down
---

# Installing Plugins

Plugins can be installed from the official **Xcore Marketplace** or from external sources like Git repositories.

## Installing from Marketplace

The easiest way to add features. `xcorecli` handles downloads and HMAC signature verification automatically.

```bash title="Marketplace Install"
xcli plugin install name-of-plugin
# Downloading name-of-plugin@2.1.0...
# Verifying HMAC signature... OK
# Installing to ./plugins/name-of-plugin/
# Plugin installed successfully.
```

### Installing a Specific Version

```bash
xcli plugin install name-of-plugin@1.2.3
```

To see all available versions for a plugin before installing:

```bash
xcli plugin versions name-of-plugin

# name-of-plugin versions:
#   2.1.0  (latest)
#   2.0.1
#   1.2.3
#   1.1.0
```

## Installing from Git or URL

Install plugins directly from a Git repository or a hosted `.zip` archive:

```bash title="Git repository"
xcli plugin install my-plugin \
  --source git \
  --url https://github.com/user/xcore-plugin.git

# Optional: specify a branch or tag
xcli plugin install my-plugin \
  --source git \
  --url https://github.com/user/xcore-plugin.git \
  --ref v1.2.0
```

```bash title="Zip archive"
xcli plugin install my-plugin \
  --source zip \
  --url https://releases.example.com/my-plugin-1.0.zip
```

## Management Commands

### Plugin Info

Get a full report on an installed plugin, including its author, description, requested permissions, and resource limits.

```bash
xcli plugin info name-of-plugin

# name-of-plugin v2.1.0
# Author: Jane Doe <jane@example.com>
# Mode:   trusted
# ─────────────────────────────────────
# Permissions:
#   db.*            read, write
#   cache.*         *
#   plugin:auth     execute
# Resources:
#   timeout:        10s
#   rate_limit:     200 calls/60s
# Signature: VALID
```

### Health Check

Verify the integrity of all installed plugins — manifests, signatures, and AST compliance for sandboxed plugins:

```bash
xcli plugin health

# Plugin Health Report
# ─────────────────────────────────────────
#   auth_plugin       OK    signed, manifest valid
#   billing_engine    WARN  plugin.sig missing
#   text_transformer  OK    sandboxed, AST clean
# ─────────────────────────────────────────
# 2 OK  1 WARNING
```

### Removal

Uninstall a plugin and remove its directory:

```bash
xcli plugin remove name-of-plugin
# Remove plugin 'name-of-plugin' and its data? [y/N]: y
# Plugin removed.
```

!!! warning "Signature Verification"
    `xcorecli` verifies the HMAC signature of marketplace plugins automatically. For Git or local installs, run `xcli plugin health` after installation to validate integrity.

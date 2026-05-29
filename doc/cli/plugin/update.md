---
title: Plugin Updates
description: Keep plugins up to date with the latest features and security patches.
icon: material/update
---

# Plugin Updates

Keep your plugins up to date with the latest features and security patches.

## Checking for Updates

Check all installed plugins against the marketplace to see if newer versions are available.

```bash title="Check Updates"
xcli plugin update check
```

## Applying Updates

The `update apply` command allows you to update a single plugin or your entire fleet.

### Update a Single Plugin

```bash
xcli plugin update apply my-plugin
```

### Update All Plugins

```bash
xcli plugin update apply --all
```

### Safe Updates (Dry Run)

See which plugins would be updated and to what versions without actually downloading anything.

```bash
xcli plugin update apply --all --dry-run
```

### Targeting a Version

```bash
xcli plugin update apply my-plugin --version 2.0.0
```

!!! warning "Breaking Changes"
    Always review the changelog on the marketplace before updating critical plugins. You can view the latest info using `xcli plugin marketplace info`.

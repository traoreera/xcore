# Marketplace Guide

The XCore Marketplace is a central repository for sharing and discovering plugins. It allows you to extend your application with pre-built components like authentication providers, payment gateways, and logging tools.

---

## 1. Using the Marketplace CLI

The `xcore marketplace` command set allows you to interact with the official registry.

### Searching for Plugins
Search by name or description:
```bash
xcore marketplace search "notification"
```

### Getting Plugin Details
View metadata, version history, and required permissions before installing:
```bash
xcore marketplace info notify-provider
```

### Installing a Plugin
Downloads the plugin and extracts it into your `./plugins` directory:
```bash
xcore marketplace install notify-provider
```

---

## 2. Marketplace Configuration

In your `xcore.yaml`, you can configure custom registry URLs or provide API keys for private marketplaces.

```yaml
marketplace:
  url: "https://marketplace.xcore.dev"
  api_key: "${MARKETPLACE_KEY}"
  timeout: 10
```

---

## 3. Security in the Marketplace

The XCore team performs automated and manual security audits on marketplace plugins:

-   **Automatic Scanning**: All plugins are scanned by the XCore `ASTScanner` and `Bandit` during submission.
-   **Verification**: "Verified" plugins undergo a manual code review.
-   **Sandboxing**: We recommend running marketplace plugins in `sandboxed` mode unless you trust the author explicitly.

---

## 4. Publishing Your Own Plugin

Coming Soon: The publishing process is currently in private beta. To join, contact the XCore team at `marketplace@xcore.dev`.

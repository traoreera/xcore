# Authentication

To interact with the **xcore marketplace** and install plugins, you need
two separate credentials — they protect different things and neither
substitutes for the other:

## Quick Start: `xcli login`

The fastest way to get both credentials — no copy-pasting required.

```bash title="Device-code login"
xcli login
```

This opens the marketplace in your browser with a 6-digit code pre-filled,
and waits. Once you confirm it there (you must already be logged into the
marketplace website, and the confirmation is an explicit click — it never
happens automatically just by opening the link), `xcli` retrieves both
credentials on its own and saves them to `~/.xcli/config.json` — the exact
same file `xcli config set` writes to, just without the manual steps.

```text
To authorize this device, visit: https://marketplace.xcorehub.dev/cli/confirm
And enter code: 042817

✓ Logged in — credentials saved to ~/.xcli/config.json
```

If the browser can't be opened automatically (headless environment, remote
shell), the URL and code are printed regardless — open it manually.

!!! info "What kind of key does this create?"
    `xcli login` mints a **personal** API key — unlike a key created
    through the marketplace's project UI (which is scoped to exactly one
    plugin or service), a personal key works for installing **any public**
    plugin or service, and any private one you own or have team access to.
    It's meant for day-to-day `xcli install`/`xcli service install` usage,
    not for CI — see [Environment variables](#environment-variables) below
    for the project-scoped alternative CI pipelines should use instead.

The device-code request expires after a few minutes if left unconfirmed;
just run `xcli login` again.

## Manual Setup

Prefer to configure credentials by hand, or need a **project-scoped** key
(tied to one specific plugin/service — the right choice for CI/CD, see
below) instead of a personal one? Both credentials can also be set directly:

| Credential | What it's for | Where to get it |
|------------|----------------|------------------|
| **API key** (`xdk_...`) | Authorizes the download itself (`X-API-Key` header on `GET /plugins/{slug}/install`) — tied to one project (`kind=plugin`, matching the target plugin's slug) | XCoreHub → Déploiements → Projets & clés |
| **Signing key** | An HMAC-SHA256 secret used to verify the `X-Signature` header on the downloaded ZIP — installation is refused if it doesn't match | XCoreHub → Déploiements → Clé de signature |

`browse`/`search`/`info` (read-only discovery) need **neither** — the
marketplace listing is public.

## Configuration Commands

`xcorecli` provides a `config` command group to manage your local settings.

### Store your credentials

```bash title="Configuration"
xcli config set api-key xdk_...
xcli config set signing-key <your-signing-secret>
```

Both are required before `xcli plugin install <name>` will succeed —
`install` checks for each explicitly and tells you exactly which one is
missing.

!!! warning "Security First"
    Never share your API key or signing key, or commit them to version
    control. They're stored in `~/.xcli/config.json` (mode `0600`), never in
    your project's `integration.yaml`.

### View current configuration

To check your current configuration (with sensitive data masked):

```bash
xcli config show
```

## Credential storage

Managed by `xcli/_credentials.py` — a flat `~/.xcli/config.json`, keyed
`api-key` / `signing-key`. Only these two keys are valid; anything else
passed to `xcli config set` is rejected.

!!! info "Marketplace URL"
    By default, `xcorecli` connects to `https://marketplace.xcorehub.dev`.
    Override it via `marketplace.url` in the project's `integration.yaml`
    (the same value the project's own backend uses) — always include the
    `https://` scheme, a bare domain will fail to resolve as a URL.

## Environment variables

For CI/CD environments, both credentials can be supplied via environment
variables instead of `xcli config set` — these take priority over
`~/.xcli/config.json` when present. Use a **project-scoped** key here (one
plugin/service, created from the marketplace's project page), not a
personal one from `xcli login` — a CI pipeline should only ever be able to
touch the one target it's meant to deploy:

```bash title=".env"
XCLI_API_KEY=xdk_...
XCLI_SIGNING_KEY=your-signing-secret
```

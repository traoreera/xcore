# Installation

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.12+ |
| uv | latest |
| xcore | installed in the environment |

xcoreSDK is the development companion to the xcore kernel. It must run inside an environment where `xcore` is importable.

---

## Install

```bash
uv add xcore-sdk
```

Or clone and install in editable mode for local development:

```bash
git clone https://github.com/traoreera/xcoreSDK
cd xcoreSDK
uv sync
```

---

## Project structure for a plugin

```
my_plugin/
├── plugin.yaml          # manifest
└── src/
    └── main.py          # Plugin class
```

### `plugin.yaml` (minimal)

```yaml
name: my_plugin
version: 1.0.0
execution_mode: trusted
```

### `src/main.py` (minimal)

```python
from xcore.sdk import AutoMixin, action, ok

class Plugin(AutoMixin):

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(pong=True)
```

---

## Verify

```bash
python - <<'EOF'
import xcore.sdk as sdk
print(dir(sdk))
EOF
```

You should see all 49 public exports listed, including `AutoMixin`, `action`, `ok`, `cached`, etc.

---

## Development workflow

```bash
# Run tests
uv run pytest

# Type-check
uv run mypy sdk/

# Build docs (from repo root)
uv run mkdocs serve
```

!!! tip "Editable install"
    When developing the SDK itself, `uv sync` installs it in editable mode so changes to `sdk/` are reflected immediately without reinstalling.

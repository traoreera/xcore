# XCore Documentation

This directory contains the complete documentation for the XCore framework.

## Structure

```
docs/
├── index.md                    # Documentation home
├── getting-started/            # Getting started guides
│   ├── installation.md         # Installation instructions
│   └── quickstart.md           # Quick start tutorial
├── guides/                       # How-to guides
│   ├── creating-plugins.md     # Plugin development
│   ├── services.md             # Working with services
│   ├── events.md               # Event system
│   └── security.md             # Security best practices
├── architecture/                 # Architecture documentation
│   └── overview.md             # System architecture
├── reference/                    # Reference documentation
│   ├── configuration.md        # Configuration reference
│   └── api.md                  # API reference
├── development/                  # Development guides
│   └── contributing.md         # Contributing guide
├── deployment/                   # Deployment guides
│   └── guide.md                # Deployment guide
└── examples/                     # Code examples
    └── complete-plugin.md      # Complete plugin example
```

## Building Documentation

### Prerequisites

```bash
pip install mkdocs-material
```

### Local Development

```bash
# Serve locally
mkdocs serve

# Build
mkdocs build

# Deploy
mkdocs gh-deploy
```

### Configuration

Documentation is configured in `mkdocs.yml` at the project root.

## Writing Guidelines

### File Format

All documentation is written in Markdown (`.md` files).

### Code Blocks

Use fenced code blocks with language:

```markdown
    ```python
    def hello():
        return "world"
    ```
```

### Admonitions

Use admonitions for notes, warnings, etc:

```markdown
!!! note
    This is a note.

!!! warning
    This is a warning.

!!! tip
    This is a tip.
```

### Links

- Internal: `[link text](path/to/file.md)`
- External: `[link text](https://example.com)`
- Anchor: `[link text](file.md#section)`

### Images

```markdown
![alt text](assets/image.png)
```

## Contributing

1. Edit files in the `docs/` directory
2. Test locally with `mkdocs serve`
3. Submit a pull request

See [Contributing Guide](development/contributing.md) for more details.

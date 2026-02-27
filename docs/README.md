# README

Documentation for XCore Framework.

## Structure

```
docs/
├── index.md                    # Documentation home
├── getting-started/            # Getting started guides
│   ├── installation.md
│   └── quickstart.md
├── guides/                     # How-to guides
│   ├── creating-plugins.md
│   ├── services.md
│   ├── events.md
│   └── security.md
├── reference/                  # API reference
│   ├── configuration.md
│   └── api.md
├── architecture/               # Architecture docs
│   └── overview.md
├── deployment/                 # Deployment guides
│   └── guide.md
└── mkdocs.yml                  # MkDocs configuration
```

## Building Documentation

### Prerequisites

```bash
pip install mkdocs-material mkdocstrings[python] mkdocs-minify-plugin
```

### Serve locally

```bash
mkdocs serve
```

### Build

```bash
mkdocs build
```

### Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

## Contributing

1. Edit Markdown files in `docs/`
2. Update `mkdocs.yml` nav if adding new pages
3. Test locally with `mkdocs serve`
4. Submit PR

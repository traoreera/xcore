"""Sphinx configuration for xcore documentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime

# Project root on sys.path for future autodoc usage.
sys.path.insert(0, os.path.abspath(".."))

project = "xcore"
author = "Eliezer Traore"
copyright = f"{datetime.now().year}, {author}"
release = "0.1.0"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Markdown support (MyST)
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
]

# HTML output
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "xcore Documentation"
html_css_files = ["custom.css"]
html_js_files = ["custom.js"]

# Cross-references
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Keep docs resilient even if some runtime deps are missing during doc build.
autodoc_mock_imports = [
    "sqlalchemy",
    "redis",
    "pymongo",
    "apscheduler",
]

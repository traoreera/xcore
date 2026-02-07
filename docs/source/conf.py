# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import datetime
import importlib.metadata

# -- Path setup --------------------------------------------------------------
# Permet à autodoc d'importer le projet
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
project = 'xcore'
author = 'xcore Team'
copyright = f'{datetime.now().year}, xcore Team'

# Version dynamique (évite les oublis)
try:
    release = importlib.metadata.version("xcore")
except importlib.metadata.PackageNotFoundError:
    release = "0.0.0"

version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'myst_parser',
    'sphinx_copybutton',
]

templates_path = ['_templates']

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

master_doc = 'index'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Autodoc configuration ---------------------------------------------------
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_default_options = {
    'members': True,
    'show-inheritance': True,
}

# -- MyST configuration ------------------------------------------------------
myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'html_admonition',
    'html_image',
    'linkify',
    'replacements',
    'smartquotes',
    'substitution',
    'tasklist',
]

myst_heading_anchors = 4

# -- HTML output -------------------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_title = "xcore Documentation"
html_show_sourcelink = True
html_show_sphinx = False

html_theme_options = {
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False,
    'style_nav_header_background': '#2980B9',
    'logo_only': True,
    'theme': 'xcore',
}

# -- Intersphinx -------------------------------------------------------------
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'fastapi': ('https://fastapi.tiangolo.com', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org', None),
}

# -- Todo --------------------------------------------------------------------
todo_include_todos = os.environ.get("SPHINX_SHOW_TODOS") == "1"

# -- Copy button -------------------------------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# -- Custom CSS --------------------------------------------------------------
def setup(app):
    app.add_css_file('custom.css')

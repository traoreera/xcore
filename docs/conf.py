# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import os as _os
import sys

# -- Path setup ---------------------------------------------------------------
# Permet d'importer les modules xcore si besoin pour autodoc
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -------------------------------------------------------
project = "xcore"
copyright = "2025, traoreera"
author = "traoreera"
release = "1.0.0"
version = "1.0"

# -- General configuration ----------------------------------------------------
extensions = [
    # Support des fichiers Markdown (.md) avec MyST
    "myst_parser",
    # Génération automatique de doc depuis les docstrings Python
    "sphinx.ext.autodoc",
    # Liens croisés entre les objets documentés
    "sphinx.ext.intersphinx",
    # Sections "todo" dans la doc (optionnel)
    "sphinx.ext.todo",
    # Graphes de dépendances entre modules
    "sphinx.ext.viewcode",
    # Résumés automatiques des modules
    "sphinx.ext.autosummary",
    # Copie des boutons pour les blocs de code
    "sphinx.ext.coverage",
]

# -- MyST Parser (Markdown) ---------------------------------------------------
myst_enable_extensions = [
    "colon_fence",  # :::{note} en plus de ```{note}
    "deflist",  # listes de définitions
    "fieldlist",  # field lists
    "html_admonition",  # <div class="note">
    "html_image",  # <img> HTML
    "linkify",  # convertit les URLs brutes en liens
    "replacements",  # remplacement de caractères (→, ©...)
    "smartquotes",  # guillemets typographiques
    "strikethrough",  # ~~texte barré~~
    "tasklist",  # - [ ] cases à cocher
]

# Numérotation automatique des titres
myst_heading_anchors = 4

# -- Fichiers sources ---------------------------------------------------------
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Fichier racine de la documentation
root_doc = "index"

# Fichiers/dossiers à exclure
exclude_patterns = [
    "_build",
    "_static",
    "_templates",
    "Thumbs.db",
    ".DS_Store",
    "**.ipynb_checkpoints",
]

# Langue par défaut
language = "fr"

# -- Options pour le thème HTML -----------------------------------------------
html_theme = "sphinx_rtd_theme"

html_theme_options = {
    # Navigation
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    # Style
    "style_nav_header_background": "#1a1a2e",
    "logo_only": False,
    # Liens externes
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
}

# Titre affiché dans la barre latérale
html_title = "xcore – Documentation"
html_short_title = "xcore"

# Logo et favicon (placez vos fichiers dans _static/)
# html_logo = "_static/logo.png"
# html_favicon = "_static/favicon.ico"

# Dossiers statiques
# Le dossier _static doit exister (même vide) pour éviter le warning Sphinx
html_static_path = ["_static"] if _os.path.isdir("_static") else []

# Templates personnalisés
templates_path = ["_templates"]

# Fichiers CSS personnalisés (chargés après le thème)
html_css_files = [
    "css/custom.css",  # design system global
    "css/index.css",  # hero + feature grid (index uniquement)
]

# Fichier JS personnalisé
html_js_files = [
    "js/custom.js",
]

# -- Options pour autodoc -----------------------------------------------------
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# -- Options pour intersphinx (liens vers docs externes) ----------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20", None),
}

# -- Options pour todo --------------------------------------------------------
todo_include_todos = True  # passer à False en production

# -- Options pour la recherche ------------------------------------------------
html_search_language = "fr"

# -- Métadonnées supplémentaires ----------------------------------------------
html_meta = {
    "description": "Documentation officielle de xcore – framework multi-plugins pour FastAPI",
    "keywords": "xcore, fastapi, plugins, python, framework",
    "author": "traoreera",
}

# -- Liens dans le footer -----------------------------------------------------
html_context = {
    "display_github": True,
    "github_user": "traoreera",
    "github_repo": "xcore",
    "github_version": "features",
    "conf_py_path": "/docs/",
}

# -- Options pour la sortie LaTeX (PDF) --------------------------------------
latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
    "preamble": r"""
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
""",
}

latex_documents = [
    (
        root_doc,
        "xcore.tex",
        "xcore Documentation",
        "traoreera",
        "manual",
    ),
]

# -- Options pour epub --------------------------------------------------------
epub_show_urls = "footnote"

# -- Autosummary --------------------------------------------------------------
autosummary_generate = True

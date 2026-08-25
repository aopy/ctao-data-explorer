# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
from importlib.metadata import PackageNotFoundError, version as get_version

# -- Project information -------------------------------------------------------
project = "CTAO Data Explorer"
copyright = "Paris Observatory / PADC & collaborators"
author = "Paris Observatory / PADC & collaborators"

try:
    release = get_version("ctao-data-explorer")
except PackageNotFoundError:
    release = os.environ.get("SETUPTOOLS_SCM_PRETEND_VERSION", "0.1.0+local")

version = release


# -- General configuration -------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_design",
    "sphinx_changelog",
    "myst_nb",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".ipynb": "myst-nb",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "**.ipynb_checkpoints", "changes"]

nb_execution_mode = os.environ.get("NB_EXECUTION_MODE", "off")
nb_execution_timeout = 120
nb_execution_raise_on_error = True


# Default language for syntax highlighting
highlight_language = "python"

# -- Options for HTML output ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/config.html#options-for-html-output


html_theme = "ctao"
html_theme_options = {
    "navigation_with_keys": False,
    # setup for displaying multiple versions, also see setup in .gitlab-ci.yml
    "switcher": {
        "json_url": "http://cta-computing.gitlab-pages.cta-observatory.org/suss/scienceportal/prototypes/ctao-data-explorer/versions.json",
        "version_match": "latest" if ".dev" in version else f"v{version}",
    },
    "navbar_center": ["version-switcher", "navbar-nav"],
    "gitlab_url": "https://gitlab.cta-observatory.org/cta-computing/suss/scienceportal/prototypes/ctao-data-explorer",
    "logo": {
        "alt_text": "ctao-logo",
        "text": " | Data Explorer",
    },
}


# Hide "Show source" link
html_show_sourcelink = False

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
}

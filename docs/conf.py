# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from importlib.metadata import version

# -- Project information -------------------------------------------------------
project = "CTAO Data Explorer"
copyright = "Paris Observatory / PADC & collaborators"
author = "Paris Observatory / PADC & collaborators"

version = version("ctao-data-explorer")
# The full version, including alpha/beta/rc tags.
release = version


# -- General configuration -------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_design",
    "sphinx_changelog",
]


source_suffix = {".rst": "restructuredtext"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "**.ipynb_checkpoints", "changes"]

# Default language for syntax highlighting
highlight_language = "python"

# -- Options for HTML output ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/config.html#options-for-html-output


html_theme = "ctao"
html_theme_options = {
    "navigation_with_keys": False,
    # setup for displaying multiple versions, also see setup in .gitlab-ci.yml
    "switcher": {
        "json_url": "https://cta-computing.gitlab-pages.cta-observatory.org/suss/scienceportal/prototypes/ctao-data-explorer/versions.json",
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

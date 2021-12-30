from unittest.mock import Mock

import sys
import os
import pathlib
import json

import urllib.request
from urllib.error import HTTPError

path = pathlib.Path(os.path.dirname(__file__))

sys.path.append(os.path.join(str(path), str(path.parent.parent)))

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../../"))
# sys.path.insert(
#     0, os.path.abspath(
#         '../../'
#     )
# )

sys.modules["__future__"] = Mock()
sys.modules["__future__.annotations"] = Mock()

print("Source files live in:", os.path.abspath("../../"))

from hisock import constants

try:
    version_html = json.loads(
        urllib.request.urlopen(
            "https://api.github.com/repos/SSS-Says-Snek/hisock/releases/latest"
        ).read()
    )
except HTTPError:
    # Most likely rate-limited
    version_html = {}

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = constants.__name__
copyright = constants.__copyright__
author = constants.__author__

html_favicon = "imgs/logo.ico"

# The full version, including alpha/beta/rc tags
try:
    release = version_html["tag_name"]
except KeyError:
    # Most likely rate-limited
    release = constants.__version__  # Fall back on latest known release

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.intersphinx",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []  # Can include '_static'

master_doc = "index"

coverage_show_missing_items = True
character_level_inline_markup = True

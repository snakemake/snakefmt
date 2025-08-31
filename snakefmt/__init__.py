import sys

"""
Version has unique source in pyproject.toml.
importlib fetches version from distribution metadata files
(in dist-info or egg-info dirs).
From Python 3.8, importlib_metadata is in standard library as importlib.metadata.
"""
from importlib import metadata

from black.mode import TargetVersion

__version__ = metadata.version("snakefmt")

# New f-string tokenizing was introduced in python 3.12 - we have to deal with it, too.
fstring_tokeniser_in_use = sys.version_info >= (3, 12)

DEFAULT_LINE_LENGTH = 88
DEFAULT_TARGET_VERSIONS = {
    TargetVersion.PY311,
    TargetVersion.PY312,
    TargetVersion.PY313,
}

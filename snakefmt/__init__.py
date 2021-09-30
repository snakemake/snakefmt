import sys

"""
Version has unique source in pyproject.toml.
importlib fetches version from distribution metadata files
(in dist-info or egg-info dirs).
From Python 3.8, importlib_metadata is in standard library as importlib.metadata.
"""
if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

__version__ = metadata.version("snakefmt")

DEFAULT_LINE_LENGTH = 88

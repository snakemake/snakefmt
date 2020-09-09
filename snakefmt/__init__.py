import importlib_metadata

"""
Version has unique source in pyproject.toml.
importlib fetches version from distribution metadata files
(in dist-info or egg-info dirs).
From Python 3.8, importlib_metadata is in standard library as importlib.metadata.
"""
__version__ = importlib_metadata.version("snakefmt")

DEFAULT_LINE_LENGTH = 88

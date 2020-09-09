from importlib import metadata

# Fetches version from distribution metadata files deriving from pyproject.toml
__version__ = metadata.version("snakefmt")

DEFAULT_LINE_LENGTH = 88

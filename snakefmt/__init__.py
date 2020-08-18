from pathlib import Path

import toml

project_fpath = Path(__file__).parent.parent / "pyproject.toml"
__version__ = toml.load(project_fpath)["tool"]["poetry"]["version"]

DEFAULT_LINE_LENGTH = 88

"""
Code for searching for and parsing snakefmt configuration files
"""

from dataclasses import fields
from pathlib import Path
from typing import Dict, Optional, Sequence, Union

import click
import toml
from black import Mode, find_project_root

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import MalformattedToml

PathLike = Union[Path, str]


def find_pyproject_toml(start_path: Sequence[str]) -> Optional[str]:
    root, _ = find_project_root(start_path)
    config_file = root / "pyproject.toml"
    return str(config_file) if config_file.is_file() else None


def read_snakefmt_config(path: Optional[str]) -> Dict[str, str]:
    """Parse Snakefmt configuration from provided toml."""
    if path is None:
        return dict()
    try:
        config_toml = toml.load(path)
        config = config_toml.get("tool", {}).get("snakefmt", {})
        config = {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}
        return config
    except (toml.TomlDecodeError, OSError) as error:
        raise click.FileError(
            filename=path, hint=f"Error reading configuration file: {error}"
        )


def inject_snakefmt_config(
    ctx: click.Context, param: click.Parameter, config_file: Optional[str] = None
) -> Optional[str]:
    """
    If no config file argument provided, parses "pyproject.toml" if one exists.
    Injects any parsed configuration into the relevant parameters to the click `ctx`.
    """
    if config_file is None:
        config_file = find_pyproject_toml(ctx.params.get("src", ()))

    config = read_snakefmt_config(config_file)

    if ctx.default_map is None:
        ctx.default_map = {}
    ctx.default_map.update(config)  # type: ignore  # bad types in .pyi
    return config_file


def read_black_config(path: Optional[PathLike]) -> Mode:
    """Parse Black configuration from provided toml."""
    black_mode = Mode(line_length=DEFAULT_LINE_LENGTH)
    if path is None:
        return black_mode
    if not Path(path).is_file():
        raise FileNotFoundError(f"{path} is not a file.")

    try:
        pyproject_toml = toml.load(path)
        config = pyproject_toml.get("tool", {}).get("black", {})
    except toml.TomlDecodeError as error:
        raise MalformattedToml(error)

    valid_black_filemode_params = sorted([field.name for field in fields(Mode)])

    for key, val in config.items():
        # this is due to FileMode param being string_normalise, but CLI being
        # skip_string_normalise - https://github.com/snakemake/snakefmt/issues/73
        if key.startswith("skip"):
            key = key[5:]
            val = not val

        key = key.replace("-", "_")
        if key not in valid_black_filemode_params:
            continue

        setattr(black_mode, key, val)
    return black_mode

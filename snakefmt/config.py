"""
Code for searching for and parsing snakefmt configuration files
"""

import tomllib
from dataclasses import fields
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union

import click
from black import Mode

from snakefmt import DEFAULT_LINE_LENGTH, DEFAULT_TARGET_VERSIONS
from snakefmt.exceptions import MalformattedToml

PathLike = Union[Path, str]


@lru_cache
def find_project_root(
    srcs: Sequence[str], stdin_filename: Optional[str] = None
) -> Tuple[Path, str]:
    """Return a directory containing .git, .hg, or pyproject.toml.

    That directory will be a common parent of all files and directories
    passed in `srcs`.

    If no directory in the tree contains a marker that would specify it's the
    project root, the root of the file system is returned.

    Returns a two-tuple with the first element as the project root path and
    the second element as a string describing the method by which the
    project root was discovered.

    Note: taken directly from black v24.1.0 as they changed the behaviour of this
    function in v24.2.0 to only find the root if the pyproject.toml file contained the
    [tool.black] section. This is not the desired behaviour for snakefmt
    """
    if stdin_filename is not None:
        srcs = tuple(stdin_filename if s == "-" else s for s in srcs)
    if not srcs:
        srcs = [str(Path.cwd().resolve())]

    path_srcs = [Path(Path.cwd(), src).resolve() for src in srcs]

    # A list of lists of parents for each 'src'. 'src' is included as a
    # "parent" of itself if it is a directory
    src_parents = [
        list(path.parents) + ([path] if path.is_dir() else []) for path in path_srcs
    ]

    common_base = max(
        set.intersection(*(set(parents) for parents in src_parents)),
        key=lambda path: path.parts,
    )

    for directory in (common_base, *common_base.parents):
        if (directory / ".git").exists():
            return directory, ".git directory"

        if (directory / ".hg").is_dir():
            return directory, ".hg directory"

        if (directory / "pyproject.toml").is_file():
            return directory, "pyproject.toml"

    return directory, "file system root"


def find_pyproject_toml(start_path: Sequence[str]) -> Optional[str]:
    root, _ = find_project_root(start_path)
    config_file = root / "pyproject.toml"
    return str(config_file) if config_file.is_file() else None


def read_snakefmt_config(path: Optional[str]) -> Dict[str, str]:
    """Parse Snakefmt configuration from provided toml."""
    if path is None:
        return dict()
    try:
        with open(path, "rb") as f:
            config_toml = tomllib.load(f)
        config = config_toml.get("tool", {}).get("snakefmt", {})
        config = {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}
        return config
    except (tomllib.TOMLDecodeError, OSError) as error:
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
    black_mode = Mode(
        line_length=DEFAULT_LINE_LENGTH, target_versions=DEFAULT_TARGET_VERSIONS
    )
    if path is None:
        return black_mode
    if not Path(path).is_file():
        raise FileNotFoundError(f"{path} is not a file.")

    try:
        with open(path, "rb") as f:
            pyproject_toml = tomllib.load(f)
        config = pyproject_toml.get("tool", {}).get("black", {})
    except tomllib.TOMLDecodeError as error:
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

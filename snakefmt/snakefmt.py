import os
from pathlib import Path
from typing import List, Union, Set, Pattern, Iterator
import logging
import re

import click
from black import get_gitignore
from pathspec import PathSpec

from snakefmt import __version__

PathLike = Union[Path, str, os.PathLike]
DEFAULT_LINE_LENGTH = 88
DEFAULT_EXCLUDES = r"/(\.snakemake|\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist)/"
DEFAULT_INCLUDES = r"/(\.smk$|^Snakefile)/"


def construct_regex(regex: str) -> Pattern[str]:
    return (
        re.compile(regex, re.VERBOSE | re.MULTILINE)
        if "\n" in regex
        else re.compile(regex)
    )


def get_snakefile_files_in_dir(
    path: Path,
    root: Path,
    include: Pattern[str],
    exclude: Pattern[str],
    gitignore: PathSpec,
) -> Iterator[Path]:
    """Generate all files under `path` whose paths are not excluded by the
    `exclude` regex, but are included by the `include` regex.
    Symbolic links pointing outside of the `root` directory are ignored.
    `report` is where output about exclusions goes.
    Adapted from
    https://github.com/psf/black/blob/ce14fa8b497bae2b50ec48b3bd7022573a59cdb1/black.py#L3519-L3573
    """
    root = root.resolve()

    for child in path.iterdir():
        # First ignore files matching .gitignore
        if gitignore.match_file(child.as_posix()):
            logging.debug(f"Ignoring: {child} matches .gitignore file content")
            continue

        # Then ignore with `exclude` option.
        try:
            normalized_path = "/" + child.resolve().relative_to(root).as_posix()
        except OSError as err:
            logging.debug(f"Ignoring: {child} cannot be read because {err}.")
            continue
        except ValueError as err:
            if child.is_symlink():
                logging.debug(
                    f"Ignoring: {child} is a symbolic link that points outside {root}"
                )
                continue
            logging.error(f"{child} caused error")
            raise ValueError(err)

        if child.is_dir():
            normalized_path += "/"

        exclude_match = exclude.search(normalized_path)
        if exclude_match and exclude_match.group(0):
            logging.debug(f"Excluded: {child} matched the --exclude regular expression")
            continue

        if child.is_dir():
            yield from get_snakefile_files_in_dir(
                child, root, include, exclude, gitignore
            )

        elif child.is_file():
            include_match = include.search(normalized_path)
            if include_match:
                logging.debug(
                    f"Included: {child} matched the --include regular expression"
                )
                yield child
            else:
                logging.debug(
                    f"Ignoring: {child} did not match the --include regular expression"
                )


@click.command()
@click.option(
    "-l", "--line-length", default=DEFAULT_LINE_LENGTH, show_default=True, type=int,
)
@click.option(
    "--include",
    type=str,
    default=DEFAULT_INCLUDES,
    help=(
        "A regular expression that matches files and directories that should be "
        "included on recursive searches.  An empty value means all files are "
        "included regardless of the name.  Use forward slashes for directories on "
        "all platforms (Windows, too).  Exclusions are calculated first, "
        "inclusions later."
    ),
    show_default=True,
)
@click.option(
    "--exclude",
    type=str,
    default=DEFAULT_EXCLUDES,
    help=(
        "A regular expression that matches files and directories that should be "
        "excluded on recursive searches.  An empty value means no paths are "
        "excluded. Use forward slashes for directories on all platforms (Windows, "
        "too). Exclusions are calculated first, inclusions later."
    ),
    show_default=True,
)
@click.argument(
    "src",
    nargs=-1,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=True, readable=True, allow_dash=True
    ),
)
@click.help_option("--help", "-h")
@click.version_option(__version__, "--version", "-V")
@click.option("-v", "--verbose", help="Turns on debug-level logging.", is_flag=True)
@click.pass_context
def main(
    ctx: click.Context,
    line_length: int,
    include: str,
    exclude: str,
    src: List[PathLike],
    verbose: bool,
):
    """The uncompromising Snakemake code formatter."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="[%(levelname)s] %(message)s", level=log_level)

    try:
        include_regex = construct_regex(include)
    except re.error:
        logging.error(f"Invalid regular expression for include given: {include!r}")
        ctx.exit(2)

    if not src:
        click.echo("No path provided. Nothing to do 😴", err=True)
        ctx.exit(0)

    sources: Set[PathLike] = set()
    root = Path()
    gitignore = get_gitignore(Path())
    for s in src:
        path = Path(s)
        if path.is_dir():
            sources.update(
                get_snakefile_files_in_dir(
                    path, root, include_regex, exclude_regex, gitignore
                )
            )
        elif p.is_file() or s == "-":
            # if a file was explicitly given, we don't care about its extension
            sources.add(path)
        else:
            logging.warning(f"ignoring invalid path: {s}")


if __name__ == "__main__":
    main()

import logging
import re
import sys
from pathlib import Path
from typing import List, Union, Set, Pattern, Iterator, Optional

import click
import toml
from black import get_gitignore
from pathspec import PathSpec

from snakefmt import __version__, DEFAULT_LINE_LENGTH
from snakefmt.formatter import Formatter
from snakefmt.parser.parser import Snakefile

sys.tracebacklimit = 0  # Disable exceptions tracebacks

PathLike = Union[Path, str]
DEFAULT_EXCLUDES = (
    r"(\.snakemake|\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|"
    r"buck-out|build|dist)"
)
DEFAULT_INCLUDES = r"(\.smk$|^Snakefile)"


class InvalidRegularExpression(Exception):
    pass


def construct_regex(regex: str) -> Pattern[str]:
    return (
        re.compile(regex, re.VERBOSE | re.MULTILINE)
        if "\n" in regex
        else re.compile(regex)
    )


def read_snakefmt_defaults_from_pyproject_toml(
    ctx: click.Context, param: click.Parameter, value: Optional[str] = None
) -> Optional[str]:
    """Inject Snakefmt configuration from "pyproject.toml" into defaults in `ctx`.
    Returns the path to a successfully found and read configuration file, None
    otherwise.
    """
    if not value:
        path = Path("pyproject.toml")
        if path.is_file():
            value = str(path)
        else:
            return None

    try:
        pyproject_toml = toml.load(value)
        config = pyproject_toml.get("tool", {}).get("snakefmt", {})
    except (toml.TomlDecodeError, OSError) as error:
        raise click.FileError(
            filename=value, hint=f"Error reading configuration file: {error}"
        )

    if not config:
        return None

    if ctx.default_map is None:
        ctx.default_map = {}
    ctx.default_map.update(  # type: ignore  # bad types in .pyi
        {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}
    )
    return value


def get_snakefiles_in_dir(
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
            normalized_path = str(child.resolve())
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

        exclude_match = exclude.search(normalized_path)
        if exclude_match and exclude_match.group(0):
            logging.debug(f"Excluded: {child} matched the --exclude regular expression")
            continue

        if child.is_dir():
            yield from get_snakefiles_in_dir(child, root, include, exclude, gitignore)

        elif child.is_file():
            include_match = include.search(child.name)
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
    "-l",
    "--line-length",
    default=DEFAULT_LINE_LENGTH,
    show_default=True,
    type=int,
    help="Lines longer than INT will be wrapped.",
    metavar="INT",
)
@click.option(
    "--include",
    type=str,
    metavar="PATTERN",
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
    metavar="PATTERN",
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
@click.option(
    "--config",
    type=click.Path(
        exists=False, file_okay=True, dir_okay=False, readable=True, allow_dash=False
    ),
    metavar="PATH",
    is_eager=True,
    callback=read_snakefmt_defaults_from_pyproject_toml,
    help=(
        "Read configuration from PATH. By default, will try to read from "
        "`./pyproject.toml`"
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
    config: Optional[PathLike],
    verbose: bool,
):
    """The uncompromising Snakemake code formatter.

    SRC specifies directories and files to format. Directories will be searched for
    file names that conform to the include/exclude patterns provided."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="[%(levelname)s] %(message)s", level=log_level)

    if not src:
        click.echo("No path provided. Nothing to do 😴", err=True)
        ctx.exit(0)

    if "-" in src and len(src) > 1:
        raise click.BadArgumentUsage("Cannot mix stdin (-) with other files")

    try:
        include_regex = construct_regex(include)
    except re.error:
        raise InvalidRegularExpression(
            f"Invalid regular expression for --include given: {include!r}"
        )

    try:
        exclude_regex = construct_regex(exclude)
    except re.error:
        raise InvalidRegularExpression(
            f"Invalid regular expression for --exclude given: {exclude!r}"
        )

    sources: Set[PathLike] = set()
    root = Path()
    gitignore = get_gitignore(Path())
    for s in src:
        path = Path(s)
        if s == "-" or path.is_file():
            # if a file was explicitly given, we don't care about its extension
            sources.add(path)
        elif path.is_dir():
            sources.update(
                get_snakefiles_in_dir(
                    path, root, include_regex, exclude_regex, gitignore
                )
            )
        else:
            logging.warning(f"ignoring invalid path: {s}")

    for s in sources:
        if s.name == "-":
            logging.info("Formatting from stdin")
            s = sys.stdin
        else:
            logging.info(f"Formatting {s}")
        snakefile = Snakefile(s)
        formatter = Formatter(snakefile, line_length=line_length, black_config=config)
        print(formatter.get_formatted())


if __name__ == "__main__":
    main()

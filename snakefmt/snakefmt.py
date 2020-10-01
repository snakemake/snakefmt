import logging
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Iterator, List, Optional, Pattern, Set, Union

import click
import toml
from black import get_gitignore
from pathspec import PathSpec

from snakefmt import DEFAULT_LINE_LENGTH, __version__
from snakefmt.diff import Diff, ExitCode
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
        return value

    if ctx.default_map is None:
        ctx.default_map = {}
    ctx.default_map.update(  # type: ignore  # bad types in .pyi
        {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}
    )
    return value


def get_snakefiles_in_dir(
    path: Path, include: Pattern[str], exclude: Pattern[str], gitignore: PathSpec,
) -> Iterator[Path]:
    """Generate all files under `path` whose paths are not excluded by the
    `exclude` regex, but are included by the `include` regex.
    Adapted from
    https://github.com/psf/black/blob/ce14fa8b497bae2b50ec48b3bd7022573a59cdb1/black.py#L3519-L3573
    """
    for child in path.iterdir():
        # First ignore files matching .gitignore
        if gitignore.match_file(child.as_posix()):
            logging.debug(f"Ignoring: {child} matches .gitignore file content")
            continue

        # Then ignore with `exclude` option.
        normalized_path = str(child.resolve().as_posix())
        exclude_match = exclude.search(normalized_path)
        if exclude_match and exclude_match.group(0):
            logging.debug(f"Excluded: {child} matched the --exclude regular expression")
            continue

        if child.is_dir():
            yield from get_snakefiles_in_dir(child, include, exclude, gitignore)

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
    "--check",
    is_flag=True,
    help=(
        f"Don't write the files back, just return the status. Return code "
        f"{ExitCode.NO_CHANGE.value} means nothing would change. Return code "
        f"{ExitCode.WOULD_CHANGE.value} means some files would be reformatted. "
        f"Return code {ExitCode.ERROR.value} means there was an error."
    ),
)
@click.option(
    "-d",
    "--diff",
    is_flag=True,
    help="Don't write the files back, just output a diff for each file to stdout.",
)
@click.option(
    "--compact-diff",
    is_flag=True,
    help=(
        "Same as --diff but only shows lines that would change plus a few lines of "
        "context."
    ),
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
    "-c",
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
    check: bool,
    diff: bool,
    compact_diff: bool,
    include: str,
    exclude: str,
    src: List[PathLike],
    config: Optional[PathLike],
    verbose: bool,
):
    """The uncompromising Snakemake code formatter.

    SRC specifies directories and files to format. Directories will be searched for
    file names that conform to the include/exclude patterns provided.

    Files are modified in-place by default; use diff, check, or
     `snakefmt - < Snakefile` to avoid this.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="[%(levelname)s] %(message)s", level=log_level)

    if not src:
        click.echo(
            "No path provided. Nothing to do 😴. Call with -h for help.", err=True
        )
        ctx.exit(0)

    if "-" in src and len(src) > 1:
        raise click.BadArgumentUsage("Cannot mix stdin (-) with other files")

    if diff and compact_diff:
        logging.warning(
            "Both --diff and --compact-diff given. Returning compact diff..."
        )

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

    files_to_format: Set[PathLike] = set()
    gitignore = get_gitignore(Path())
    for path in src:
        path = Path(path)
        if path.name == "-" or path.is_file():
            # if a file was explicitly given, we don't care about its extension
            files_to_format.add(path)
        elif path.is_dir():
            files_to_format.update(
                get_snakefiles_in_dir(path, include_regex, exclude_regex, gitignore)
            )
        else:
            logging.warning(f"ignoring invalid path: {path}")

    differ = Diff(compact=compact_diff)
    files_changed, files_unchanged = 0, 0
    files_with_errors = 0
    for path in files_to_format:
        path_is_stdin = path.name == "-"
        if path_is_stdin:
            logging.debug("Formatting from stdin")
            path = sys.stdin
        else:
            logging.debug(f"Formatting {path}")

        try:
            original_content = path.read_text()
        except AttributeError:
            original_content = path.read()

        try:
            snakefile = Snakefile(StringIO(original_content))
            formatter = Formatter(
                snakefile, line_length=line_length, black_config=config
            )
            formatted_content = formatter.get_formatted()
        except Exception as error:
            if check:
                logging.error(f"'{error.__class__.__name__}: {error}' in file {path}")
                files_with_errors += 1
                continue
            else:
                raise error

        if check:
            is_changed = differ.is_changed(original_content, formatted_content)
            if is_changed:
                logging.debug("Formatted content is different from original")
                files_changed += 1
            else:
                files_unchanged += 1

        if diff or compact_diff:
            filename = "stdin" if path_is_stdin else str(path)
            click.echo(f"{'=' * 5}> Diff for {filename} <{'=' * 5}\n")
            difference = differ.compare(original_content, formatted_content)
            click.echo(difference)
        elif not any([check, diff, compact_diff]):
            if path_is_stdin:
                sys.stdout.write(formatted_content)
            else:
                write_file_back = differ.is_changed(original_content, formatted_content)
                if write_file_back:
                    logging.info(f"Writing formatted content to {path}")
                    with path.open("w") as out_handle:
                        out_handle.write(formatted_content)

    if check:
        if files_unchanged == len(files_to_format):
            logging.info(
                f"All {len(files_to_format)} file(s) would be left unchanged 🎉"
            )
            ctx.exit(ExitCode.NO_CHANGE.value)
        elif files_with_errors > 0:
            exit_value = ExitCode.ERROR.value
        elif files_changed > 0:
            exit_value = ExitCode.WOULD_CHANGE.value

        if files_with_errors > 0:
            logging.info(f"{files_with_errors} file(s) raised parsing errors 🤕")
        if files_changed > 0:
            logging.info(f"{files_changed} file(s) would be changed 😬")
        if files_unchanged > 0:
            logging.info(f"{files_unchanged} file(s) would be left unchanged 🎉")
        ctx.exit(exit_value)

    logging.info("All done 🎉")


if __name__ == "__main__":
    main()

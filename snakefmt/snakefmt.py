import os
from pathlib import Path
from typing import List, Union

import click

from snakefmt import __version__

PathLike = Union[Path, str, os.PathLike]
DEFAULT_LINE_LENGTH = 88


@click.command()
@click.help_option("--help", "-h")
@click.version_option(__version__, "--version", "-V")
@click.option(
    "-l", "--line-length", default=DEFAULT_LINE_LENGTH, show_default=True, type=int,
)
@click.argument(
    "src",
    nargs=-1,
    type=click.Path(exists=True, writable=True, allow_dash=True),
    required=True,
)
def main(line_length: int, src: List[str]):
    """The uncompromising Snakemake code formatter."""
    for p in src:
        print(f"Got file {p}")


if __name__ == "__main__":
    main()

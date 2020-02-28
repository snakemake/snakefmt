import click

DEFAULT_LINE_LENGTH = 88


@click.command()
@click.help_option("--help", "-h")
@click.option(
    "-l",
    "--line-length",
    default=DEFAULT_LINE_LENGTH,
    show_default=True,
    type=click.IntRange(min=1),
)
def main():
    """The uncompromising Snakemake code formatter."""
    print("Hello world")


if __name__ == "__main__":
    main()

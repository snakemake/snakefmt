from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakefmt.config import Mode
    from snakefmt.formatter.state import FormatState
    from snakefmt.parser.snakefile import Snakefile


def _newline_style(source: str) -> str:
    """The line ending used by ``source``.

    Only ``\r\n`` is distinguished from ``\n``: a file is treated as CRLF when
    it contains a CRLF line ending and no bare-LF line ending.
    """
    if "\r\n" not in source:
        return "\n"
    without_crlf = source.replace("\r\n", "")
    return "\r\n" if "\n" not in without_crlf else "\n"


class Formatter:
    """A parsed `Snakefile` together with the `FormatState` and `Mode` used to
    format it. `setup` is the equivalent of the old `setup_formatter`."""

    def __init__(
        self,
        snakefile: "Snakefile",
        state: "FormatState",
        mode: "Mode",
        newline: str = "\n",
    ):
        self.snakefile = snakefile
        self.state = state
        self.black_mode = mode
        self.newline = newline

    def get_formatted(self) -> str:
        from snakefmt.formatter.segments import format_snakefile

        formatted = format_snakefile(self.snakefile, self.black_mode, self.state)
        if self.newline != "\n":
            formatted = formatted.replace("\n", self.newline)
        return formatted

    @classmethod
    def setup(
        cls,
        snake: str,
        line_length: int | None = None,
        sort_directives=False,
        black_config_file=None,
        format_shell=False,
        directive_order: tuple[str, ...] = (),
        module_directive_order: tuple[str, ...] = (),
    ):
        from snakefmt.config import Mode, read_black_config
        from snakefmt.formatter.state import FormatState
        from snakefmt.parser.snakefile import Snakefile

        newline = _newline_style(snake)
        snake = snake.replace("\r\n", "\n")
        snakefile = Snakefile.parse(snake)
        mode = read_black_config(black_config_file) or Mode()
        if line_length is not None:
            mode.line_length = line_length
        state = FormatState(
            sort_directives=sort_directives or None,
            format_shell=format_shell,
            rule_order=tuple(directive_order),
            module_order=tuple(module_directive_order),
        )
        return cls(snakefile, state, mode, newline)

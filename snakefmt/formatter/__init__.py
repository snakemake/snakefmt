from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakefmt.config import Mode
    from snakefmt.formatter.state import FormatState
    from snakefmt.parser.snakefile import Snakefile


class Formatter:
    """A parsed `Snakefile` together with the `FormatState` and `Mode` used to
    format it. `setup` is the equivalent of the old `setup_formatter`."""

    def __init__(self, snakefile: "Snakefile", state: "FormatState", mode: "Mode"):
        self.snakefile = snakefile
        self.state = state
        self.mode = mode

    def get_formatted(self) -> str:
        from snakefmt.formatter.segments import format_snakefile

        return format_snakefile(self.snakefile, self.mode, self.state)

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
        return cls(snakefile, state, mode)

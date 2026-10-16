import tokenize
from typing import Callable

from snakefmt.config import Mode, read_black_config
from snakefmt.formatter.formatter import format_snakefile
from snakefmt.formatter.state import FormatState
from snakefmt.parser.blocks import Block, python_subautomata
from snakefmt.parser.directives import global_snakemake_subautomata
from snakefmt.parser.tokens import TokenIterator


class GlobalBlock(Block):
    """Hold `body_blocks` only, no `head_lines` nor `tail_noncoding`

    all blocks in `body_blocks` should in the
      same deindent level as GlobalBlock itself
    so tail_noncoding always updated to the last body_block
    """

    __slots__ = ()

    subautomata = {**python_subautomata, **global_snakemake_subautomata}

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    def compilation(self):
        raise NotImplementedError


class Snakefile(GlobalBlock):
    """The parsed root of a Snakemake file.

    Holds the configuration needed to format it; the formatting itself is done
    by the external `format_snakefile`.
    """

    __slots__ = ("mode", "state")
    mode: Mode
    state: FormatState

    def get_formatted(self, mode: Mode | None = None):
        if mode is None:
            mode = getattr(self, "mode", None)
            if mode is None:
                raise ValueError("Mode should be provided for formatting")
        state = getattr(self, "state", None)
        if state is None:
            state = FormatState()
        return format_snakefile(self, mode, state)


def parse(source: str | Callable[[], str], name: str = "<string>"):
    if isinstance(source, str):
        tokens = tokenize.generate_tokens(
            iter(source.splitlines(keepends=True)).__next__
        )
    else:
        tokens = tokenize.generate_tokens(source)
    return Snakefile(0, TokenIterator(name, tokens), [])


def setup_formatter(
    snake: str,
    line_length: int | None = None,
    sort_directives: bool = False,
    black_config_file=None,
    format_shell=False,
    directive_order: tuple[str, ...] = (),
    module_directive_order: tuple[str, ...] = (),
):
    formatter = parse(snake)
    mode = read_black_config(black_config_file) or Mode()
    if line_length is not None:
        mode.line_length = line_length

    formatter.mode = mode
    formatter.state = FormatState(
        sort_directives=sort_directives or None,
        format_shell=format_shell,
        rule_order=tuple(directive_order),
        module_order=tuple(module_directive_order),
    )
    return formatter

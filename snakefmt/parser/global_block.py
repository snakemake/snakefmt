import tokenize
from typing import Callable

from snakefmt.config import Mode, read_black_config
from snakefmt.parser.blocks import Block, python_subautomata
from snakefmt.parser.directives import global_snakemake_subautomata
from snakefmt.parser.formatting import FormatState
from snakefmt.parser.tokens import TokenIterator

from . import formatting


class GlobalBlock(Block):
    """Hold `body_blocks` only, no `head_lines` nor `tail_noncoding`

    all blocks in `body_blocks` should in the
      same deindent level as GlobalBlock itself
    so tail_noncoding always updated to the last body_block
    """

    __slots__ = (
        "mode",
        "sort_directives",
        "format_shell",
        "directive_order",
        "module_directive_order",
    )
    mode: Mode
    sort_directives: bool
    format_shell: bool
    directive_order: tuple[str, ...]
    module_directive_order: tuple[str, ...]

    subautomata = {**python_subautomata, **global_snakemake_subautomata}

    def __init__(self, deindent_level, tokens, lines=None):
        super().__init__(deindent_level, tokens, lines)

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    def get_formatted(
        self,
        mode: Mode | None = None,
        sort_directives: bool | None = None,
        format_shell: bool | None = None,
    ):
        if mode is None:
            mode = getattr(self, "mode", None)
            if mode is None:
                raise ValueError("Mode should be provided for formatting")
        if sort_directives is None:
            sort_directives = getattr(self, "sort_directives", None)
        if format_shell is None:
            format_shell = bool(getattr(self, "format_shell", False))
        state = FormatState(
            sort_directives=sort_directives or None,
            format_shell=format_shell,
            rule_order=tuple(getattr(self, "directive_order", ()) or ()),
            module_order=tuple(getattr(self, "module_directive_order", ()) or ()),
        )
        # if set to None, it will not be enabled by `# fmt: on`
        python_codes: list[str] = []
        snakemake_codes: list[tuple[str, str]] = []
        last_str = ""
        for segment, indent_proxy in self.segment2format(mode or self.mode, state):
            if indent_proxy is not None:
                python_codes.append(last_str)
                last_str = ""
                snakemake_codes.append((segment, indent_proxy))
            else:
                last_str += segment
        placeholder = "o" * 50
        raw_str = "".join(python_codes)
        while placeholder in raw_str:
            placeholder *= 2
        raw_str = "#\n"
        for python_code, (snakemake_code, indent) in zip(python_codes, snakemake_codes):
            if snakemake_code.count("\n") == 1:  # must at the end of line
                snakemake_proxy = f"{indent}def l{placeholder}1ng(): ...\n"
            else:
                snakemake_proxy = f"{indent}def l{placeholder}ng():\n{indent} return\n"
            raw_str += python_code + snakemake_proxy
        raw_str += last_str
        formatted, *formatted_split = formatting.format_black(raw_str, mode).split(
            placeholder
        )
        final_str = formatted
        for formatted, (snakemake_code, _) in zip(formatted_split, snakemake_codes):
            final_str = final_str.rsplit("\n", 1)[0] + "\n" + snakemake_code
            if formatted.startswith("1"):
                final_str += formatted.split("\n", 1)[-1]
            else:
                final_str += formatted.split("\n", 2)[-1]
        return final_str[1:].lstrip("\n")

    def compilation(self):
        raise NotImplementedError


def parse(source: str | Callable[[], str], name: str = "<string>"):
    if isinstance(source, str):
        tokens = tokenize.generate_tokens(
            iter(source.splitlines(keepends=True)).__next__
        )
    else:
        tokens = tokenize.generate_tokens(source)
    return GlobalBlock(0, TokenIterator(name, tokens), [])


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
    formatter.sort_directives = sort_directives
    formatter.format_shell = format_shell
    formatter.directive_order = tuple(directive_order)
    formatter.module_directive_order = tuple(module_directive_order)
    return formatter

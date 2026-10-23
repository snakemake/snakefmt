import tokenize
from typing import TYPE_CHECKING, Iterable

from snakefmt.config import Mode
from snakefmt.formatter import black
from snakefmt.formatter.blocks import format_block
from snakefmt.formatter.indent import TAB, deindent_lines
from snakefmt.formatter.state import FormatState
from snakefmt.parser.blocks import Block, ColonBlock
from snakefmt.parser.snakemake_blocks import SnakemakeBlock
from snakefmt.parser.tokens import LogicalLine, tokens2linestrs

if TYPE_CHECKING:
    from snakefmt.parser.snakefile import Snakefile


def _count(text: str):
    return text.count("\n") + (bool(text) and not text.endswith("\n"))


def _segment_origins(origin: int | None, text: str) -> list[int | None]:
    count = _count(text)
    if origin is None:
        return [None] * count
    return list(range(origin, origin + count))


def _origin(line: LogicalLine) -> int:
    for token in line.iter:
        if token.type == tokenize.DEDENT:
            continue
        return token.start[0]
    raise ValueError(f"Cannot determine origin of empty line: {line}")


def _format_head(head_lines: list[LogicalLine]):
    for line in head_lines:
        origin = _origin(line)
        for line in line.linestrs:
            yield origin, line, None
            origin += _count(line)


def format_segments(
    block: Block, mode: Mode, state: FormatState
) -> Iterable[tuple[int | None, str, str | None]]:
    """yield:
    - [origin_line_nb | None, unformated_python_code, None]
    - [None, formated_snakemake_code, indent_str]

    `SnakemakeInlineArgumentBlock` should be taken very careful of,
    since they are formatedd as `def` blocks, and may not sperate from
    blocks with different keywords. So here are the special principles
    specially for one-line snakemake blocks:

    - the previous block should be in the same indent of current block;
    - if previous line (with no newline nor comments) is:
            1, `def` block; or
            2. another one-line block with differnt keyword:
        then add a newline
    - if previous line is the same keyword with:
            only comment lines but NO blank line between:
        merge the two lines into one block, with comments in between
    - (doesn't matter if this block is actually one-line or not)
    """
    # comment fmt directives in head_linestrs
    #  will effect on post blocks of the same indent,
    # so should be updated during the parent body_blocks iteration.
    yield from _format_head(block.head_lines)
    last_keyword = ""
    line = ""
    state = state.reset_sort()
    for sub in block.body_blocks:
        restart_state = state = state.consume_skip_next()
        # update state from head_noncoding
        for head_line in sub.head_lines:
            for noncoding_token in head_line.head_noncoding:
                if noncoding_token.type == tokenize.COMMENT:
                    state = state.update(noncoding_token.string)
                elif state.skip_next and not noncoding_token.line.strip():
                    state = state.consume_skip_next()
        if isinstance(sub, ColonBlock):
            if sub.keyword == "def":
                if last_keyword and last_keyword != "def":
                    # Oh, differnt keyword detected, so (last)line must exists
                    # Then check if that line is start
                    if (
                        line.rstrip()
                        .rsplit("\n", 1)[-1]
                        .startswith(sub.indent_str + last_keyword)
                    ):
                        # If NO any line before the first line of this block,
                        # black cannot split them: Add one to force splitting
                        if not sub.head_lines[0].head_noncoding:
                            yield None, "\n", None
                last_keyword = "def"
                for origin, line, indent in format_segments(sub, mode, state):
                    # record `line` for next useage
                    yield origin, line, indent
            elif isinstance(sub, SnakemakeBlock):
                for origin, line, indent in format_snakemake_segments(
                    sub, mode, restart_state, last_keyword
                ):
                    yield origin, line, indent
                last_keyword = sub.keyword
            else:
                last_keyword = ""
                yield from format_segments(sub, mode, state)
        else:
            last_keyword = ""
            yield from format_segments(sub, mode, state)
    yield from _format_tail(block.tail_noncoding)


def _format_tail(tail: list[tokenize.TokenInfo]):
    if tail:
        origin = tail[0].start[0]
        for text in tokens2linestrs(iter(tail)):
            yield origin, text, None
            origin += _count(text)


def format_snakemake_segments(
    block: SnakemakeBlock, mode: Mode, state: FormatState, last_keyword=""
) -> Iterable[tuple[int | None, str, str | None]]:
    """yield:
    - [origin_line_nb | None, unformated_python_code, None]
    - [None, formated_snakemake_code, indent]

    If state.skip_next is True, or state.fmt_on is False,
    return unformatted content with proper True/False markers.

    Decorator head lines are emitted as Python code; the final head line (the
    Snakemake keyword line) is formatted as usual.
    """
    indent_str = TAB * block.deindent_level
    prefix_lines = block.head_lines[:-1]
    # Who knows if somebody wraps snakemake block?
    for line in prefix_lines:
        for noncoding_line in tokens2linestrs(iter(line.head_noncoding)):
            if not noncoding_line.strip():
                last_keyword = ""
            else:
                state = state.update(noncoding_line.lstrip())
    yield from _format_head(prefix_lines)

    noncoding_lines: list[str] = []
    last_fmt_on = state.fmt_on
    # Check if there's fmt: on/off in noncoding_lines to update state
    for noncoding_line in tokens2linestrs(iter(block.colon_line.head_noncoding)):
        if not noncoding_line.strip():
            last_keyword = ""
        else:
            state = state.update(noncoding_line.lstrip())
        if state.not_format:
            noncoding_lines.append(noncoding_line)
        else:
            noncoding_lines.append(
                indent_str + black.format_python(noncoding_line, mode, 0)
            )
    if last_fmt_on and state.fmt_on:
        if last_keyword == block.keyword:
            # pre-format these lines and yield together
            pre_formatted = black.format_python(
                "".join(noncoding_lines), mode, 0
            ).splitlines(keepends=True)
            for line in pre_formatted:
                if state.found_skip(line):
                    yield None, line, None
                else:
                    yield None, indent_str + line.lstrip(), block.indent_str
        else:
            if not noncoding_lines and not prefix_lines:
                yield None, "\n", None
            yield None, "".join(noncoding_lines), None
    else:
        yield None, "".join(noncoding_lines), None

    # Check if this block should be skipped from formatting
    if state.not_format:
        raw = "".join(
            deindent_lines(
                block.indent_str,
                block.deindent_level,
                block.raw_source_linestrs(),
            )
        )
        # Trailing blank lines from body_blocks belong to the next block's
        # separator, not this block's content. Strip extra trailing blank
        # lines so the compilation loop doesn't double-count them with
        # black's blank-line insertion.
        if raw.endswith("\n\n") and state.skip_next:
            n_trailing_space = len(raw) - len(raw.rstrip("\n")) - 1
            raw = raw.rstrip("\n") + "\n"
        else:
            n_trailing_space = 0
        yield None, raw, block.indent_str
        if n_trailing_space > 0:
            yield None, "\n" * n_trailing_space, None
    else:
        yield None, format_block(block, mode, state), block.indent_str
    yield from _format_tail(block.tail_noncoding)


def format_snakefile(snakefile: "Snakefile", mode: Mode, state: FormatState) -> str:
    """Format a parsed `Snakefile` under `state`."""
    # if set to None, it will not be enabled by `# fmt: on`
    python_codes: list[str] = []
    snakemake_codes: list[tuple[str, str]] = []
    python_origins: list[list[int | None]] = []
    last_str = ""
    last_origins: list[int | None] = []
    for origin, segment, indent_proxy in format_segments(snakefile, mode, state):
        if indent_proxy is not None:
            python_codes.append(last_str)
            python_origins.append(last_origins)
            last_str = ""
            last_origins = []
            snakemake_codes.append((segment, indent_proxy))
        else:
            last_str += segment
            last_origins.extend(_segment_origins(origin, segment))
    placeholder = "o" * 50
    raw_str = "".join(python_codes) + last_str
    while placeholder in raw_str:
        placeholder *= 2
    raw_str = "#\n"
    line_map: list[int | None] = [None]
    for python_code, origins, (snakemake_code, indent) in zip(
        python_codes, python_origins, snakemake_codes
    ):
        raw_str += python_code
        line_map.extend(origins)
        if snakemake_code.count("\n") == 1:  # must at the end of line
            snakemake_proxy = f"{indent}def l{placeholder}1ng(): ...\n"
            proxy_lines = 1
        else:
            snakemake_proxy = f"{indent}def l{placeholder}ng():\n{indent} return\n"
            proxy_lines = 2
        raw_str += snakemake_proxy
        line_map.extend([None] * proxy_lines)
    raw_str += last_str
    line_map.extend(last_origins)
    formatted, *formatted_split = black.format_python(
        raw_str, mode, line_map=line_map
    ).split(placeholder)
    final_str = formatted
    for formatted, (snakemake_code, _) in zip(formatted_split, snakemake_codes):
        final_str = final_str.rsplit("\n", 1)[0] + "\n" + snakemake_code
        if formatted.startswith("1"):
            final_str += formatted.split("\n", 1)[-1]
        else:
            final_str += formatted.split("\n", 2)[-1]
    return final_str[1:].lstrip("\n")
